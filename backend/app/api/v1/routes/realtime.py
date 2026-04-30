from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.ai_provider import generate_chat_completion
from app.core.collaboration_store import collaboration_store
from app.core.persona_prompt import compile_persona_system_prompt
from app.core.realtime_manager import realtime_manager
from app.core.security import decode_jwt
from app.core.studio_store import studio_store
from app.core.tenant_policy import require_existing_tenant, validate_tenant_scope

router = APIRouter(tags=["realtime"])

_pending_ai_tasks: dict[str, asyncio.Task[None]] = {}


def _cancel_pending_ai(channel_id: str) -> None:
    task = _pending_ai_tasks.get(channel_id)
    if task and not task.done():
        task.cancel()


def _is_persona_allowed_for_org(
    *,
    tenant_id: str,
    org_id: str,
    persona: dict[str, object] | None,
) -> bool:
    if persona is None:
        return True
    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    mode = str(org_settings.get("prompt_policy_mode", "open"))
    if mode in {"approval_required", "allowlist_only"}:
        return str(persona.get("approval_status", "")) == "approved"
    return True


def _select_council_head(
    *,
    personas: list[dict[str, Any]],
    room_personas: list[dict[str, Any]],
    configured_head_persona_id: str | None,
) -> dict[str, Any] | None:
    if configured_head_persona_id:
        for persona in personas:
            if persona.get("persona_id") == configured_head_persona_id:
                return persona

    head_ids = {
        str(item.get("persona_id"))
        for item in room_personas
        if str(item.get("role_in_room", "")).lower() == "head"
    }
    if head_ids:
        for persona in personas:
            if str(persona.get("persona_id")) in head_ids:
                return persona

    return personas[0] if personas else None


async def _generate_persona_completion(
    *,
    tenant_id: str,
    channel_id: str,
    persona: dict[str, Any],
) -> dict[str, Any]:
    messages = collaboration_store.build_conversation_messages(
        tenant_id=tenant_id,
        channel_id=channel_id,
        limit=40,
    )
    result = await asyncio.to_thread(
        generate_chat_completion,
        system_prompt=compile_persona_system_prompt(persona),
        conversation_messages=messages,
        model_profile=str(persona.get("model_profile", "reasoning-optimized")),
    )
    return {
        "persona_id": persona.get("persona_id"),
        "persona_name": persona.get("name"),
        "content": result.content,
        "provider": result.provider,
        "model": result.model,
        "usage": result.usage,
    }


async def _run_single_best_ai(
    *,
    tenant_id: str,
    user_id: str,
    channel_id: str,
    persona_id: str | None,
    delay_seconds: int,
) -> None:
    room = f"tenant:{tenant_id}:channel:{channel_id}"
    await realtime_manager.publish(
        room=room,
        event={
            "event": "chat.response.pending",
            "channel_id": channel_id,
            "delay_seconds": delay_seconds,
            "mode": "single_best",
        },
    )
    await asyncio.sleep(max(delay_seconds, 0))

    channel = collaboration_store.get_channel(tenant_id=tenant_id, channel_id=channel_id)
    if channel is None:
        return
    org_id = str(channel.get("org_id", ""))

    selected_persona = None
    resolved_persona_id = persona_id or channel.get("default_persona_id")
    if resolved_persona_id:
        selected_persona = collaboration_store.get_persona(
            tenant_id=tenant_id,
            persona_id=resolved_persona_id,
        )

    system_prompt = ""
    model_profile = "reasoning-optimized"
    if selected_persona:
        if org_id and not _is_persona_allowed_for_org(
            tenant_id=tenant_id,
            org_id=org_id,
            persona=selected_persona,
        ):
            await realtime_manager.publish(
                room=room,
                event={
                    "event": "chat.response.skipped",
                    "channel_id": channel_id,
                    "reason": "persona_not_approved",
                },
            )
            return
        system_prompt = compile_persona_system_prompt(selected_persona)
        model_profile = selected_persona.get("model_profile", "reasoning-optimized")

    messages = collaboration_store.build_conversation_messages(
        tenant_id=tenant_id,
        channel_id=channel_id,
        limit=40,
    )

    try:
        result = await asyncio.to_thread(
            generate_chat_completion,
            system_prompt=system_prompt,
            conversation_messages=messages,
            model_profile=model_profile,
        )
    except Exception as error:
        await realtime_manager.publish(
            room=room,
            event={
                "event": "chat.response.failed",
                "channel_id": channel_id,
                "message": str(error),
            },
        )
        return

    assistant_message = collaboration_store.create_channel_message(
        tenant_id=tenant_id,
        channel_id=channel_id,
        sender_user_id=user_id,
        content=result.content,
        metadata={
            "sender_kind": "assistant",
            "provider": result.provider,
            "model": result.model,
            "usage": result.usage,
            "persona_id": selected_persona.get("persona_id") if selected_persona else None,
            "mode": "single_best",
        },
    )

    await realtime_manager.publish(
        room=room,
        event={
            "event": "chat.response.completed",
            "channel_id": channel_id,
            "message": assistant_message,
        },
    )


async def _run_council_ai(
    *,
    tenant_id: str,
    user_id: str,
    channel_id: str,
    requested_mode: str,
    delay_ms: int,
) -> None:
    room = f"tenant:{tenant_id}:channel:{channel_id}"
    await realtime_manager.publish(
        room=room,
        event={
            "event": "council.delayed_start",
            "channel_id": channel_id,
            "delay_ms": delay_ms,
        },
    )
    await asyncio.sleep(max(delay_ms, 0) / 1000)

    channel = collaboration_store.get_channel(tenant_id=tenant_id, channel_id=channel_id)
    if channel is None:
        return
    org_id = str(channel.get("org_id", ""))

    config = collaboration_store.get_room_council_config(tenant_id=tenant_id, room_id=channel_id) or {}
    room_personas = collaboration_store.list_room_personas(tenant_id=tenant_id, room_id=channel_id)
    active_room_personas = [item for item in room_personas if bool(item.get("is_active", True))]

    if not active_room_personas:
        await realtime_manager.publish(
            room=room,
            event={
                "event": "chat.response.skipped",
                "channel_id": channel_id,
                "reason": "no_room_personas",
            },
        )
        return

    personas: list[dict[str, Any]] = []
    for room_persona in active_room_personas:
        persona_id = str(room_persona.get("persona_id", ""))
        if not persona_id:
            continue
        persona = collaboration_store.get_persona(tenant_id=tenant_id, persona_id=persona_id)
        if persona is None or not bool(persona.get("enabled", True)):
            continue
        if not _is_persona_allowed_for_org(tenant_id=tenant_id, org_id=org_id, persona=persona):
            continue
        personas.append(persona)

    if not personas:
        await realtime_manager.publish(
            room=room,
            event={
                "event": "chat.response.skipped",
                "channel_id": channel_id,
                "reason": "no_approved_personas",
            },
        )
        return

    council_mode = requested_mode
    if requested_mode == "council":
        council_mode = str(config.get("council_mode", "summarized"))
    if council_mode not in {"summarized", "threaded", "silent_head"}:
        council_mode = "summarized"

    allow_parallel = bool(config.get("allow_parallel_responses", False))

    try:
        if allow_parallel:
            responses = await asyncio.gather(
                *[
                    _generate_persona_completion(
                        tenant_id=tenant_id,
                        channel_id=channel_id,
                        persona=persona,
                    )
                    for persona in personas
                ]
            )
        else:
            responses: list[dict[str, Any]] = []
            for persona in personas:
                responses.append(
                    await _generate_persona_completion(
                        tenant_id=tenant_id,
                        channel_id=channel_id,
                        persona=persona,
                    )
                )
    except Exception as error:
        await realtime_manager.publish(
            room=room,
            event={
                "event": "chat.response.failed",
                "channel_id": channel_id,
                "message": str(error),
            },
        )
        return

    if council_mode in {"threaded", "silent_head"}:
        for response in responses:
            message = collaboration_store.create_channel_message(
                tenant_id=tenant_id,
                channel_id=channel_id,
                sender_user_id=user_id,
                content=response["content"],
                metadata={
                    "sender_kind": "assistant",
                    "provider": response["provider"],
                    "model": response["model"],
                    "usage": response["usage"],
                    "persona_id": response["persona_id"],
                    "persona_name": response["persona_name"],
                    "mode": council_mode,
                    "orchestration": "council",
                },
            )
            await realtime_manager.publish(
                room=room,
                event={
                    "event": "chat.response.persona",
                    "channel_id": channel_id,
                    "message": message,
                },
            )
        return

    council_head = _select_council_head(
        personas=personas,
        room_personas=active_room_personas,
        configured_head_persona_id=(
            str(config.get("council_head_persona_id", "")) or None
        ),
    )
    if council_head is None:
        council_head = personas[0]

    summary_input = "\n\n".join(
        [
            f"[{response['persona_name'] or response['persona_id']}] {response['content']}"
            for response in responses
        ]
    )
    summary_messages = [
        {
            "role": "user",
            "content": (
                "Synthesize the following council responses into a single actionable response. "
                "Retain key points and disagreements where relevant.\n\n"
                f"{summary_input}"
            ),
        }
    ]

    try:
        summary_result = await asyncio.to_thread(
            generate_chat_completion,
            system_prompt=compile_persona_system_prompt(council_head),
            conversation_messages=summary_messages,
            model_profile=str(council_head.get("model_profile", "reasoning-optimized")),
        )
    except Exception as error:
        await realtime_manager.publish(
            room=room,
            event={
                "event": "chat.response.failed",
                "channel_id": channel_id,
                "message": str(error),
            },
        )
        return

    summary_message = collaboration_store.create_channel_message(
        tenant_id=tenant_id,
        channel_id=channel_id,
        sender_user_id=user_id,
        content=summary_result.content,
        metadata={
            "sender_kind": "assistant",
            "provider": summary_result.provider,
            "model": summary_result.model,
            "usage": summary_result.usage,
            "persona_id": council_head.get("persona_id"),
            "persona_name": council_head.get("name"),
            "mode": "summarized",
            "orchestration": "council",
            "council_responses": responses,
        },
    )
    await realtime_manager.publish(
        room=room,
        event={
            "event": "council.response",
            "channel_id": channel_id,
            "message": summary_message,
        },
    )


@router.websocket("/realtime/ws")
@router.websocket("/ws")
async def realtime_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return

    try:
        claims = decode_jwt(token)
    except ValueError:
        await websocket.close(code=4401, reason="invalid token")
        return

    if claims.get("token_type") != "access":
        await websocket.close(code=4401, reason="access token required")
        return

    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    if not isinstance(tenant_id, str) or not isinstance(user_id, str):
        await websocket.close(code=4401, reason="invalid token claims")
        return

    try:
        validate_tenant_scope(tenant_id)
        require_existing_tenant(tenant_id)
    except Exception:
        await websocket.close(code=4403, reason="tenant forbidden")
        return

    await realtime_manager.connect(websocket)
    user_room = f"tenant:{tenant_id}:user:{user_id}"
    realtime_manager.subscribe(room=user_room, websocket=websocket)

    org_id_claim = claims.get("org_id")
    if isinstance(org_id_claim, str) and org_id_claim:
        realtime_manager.subscribe(room=f"tenant:{tenant_id}:org:{org_id_claim}", websocket=websocket)

    try:
        await websocket.send_json(
            {
                "event": "system.connected",
                "tenant_id": tenant_id,
                "user_id": user_id,
            }
        )

        while True:
            payload = await websocket.receive_json()
            action = payload.get("action") if isinstance(payload, dict) else None

            if action == "subscribe":
                room = payload.get("room")
                if isinstance(room, str) and room.startswith(f"tenant:{tenant_id}:"):
                    realtime_manager.subscribe(room=room, websocket=websocket)
                    await websocket.send_json({"event": "system.subscribed", "room": room})
                else:
                    await websocket.send_json(
                        {
                            "event": "system.error",
                            "message": "invalid room subscription",
                        }
                    )
                continue

            if action == "publish":
                room = payload.get("room")
                event = payload.get("event")
                if isinstance(room, str) and room.startswith(f"tenant:{tenant_id}:") and isinstance(event, dict):
                    await realtime_manager.publish(room=room, event=event)
                else:
                    await websocket.send_json(
                        {"event": "system.error", "message": "invalid publish payload"}
                    )
                continue

            if action == "chat.typing":
                channel_id = payload.get("channel_id")
                state = payload.get("state")
                if isinstance(channel_id, str):
                    room = f"tenant:{tenant_id}:channel:{channel_id}"
                    if state == "started":
                        _cancel_pending_ai(channel_id)
                        await realtime_manager.publish(
                            room=room,
                            event={
                                "event": "chat.response.cancelled",
                                "channel_id": channel_id,
                                "reason": "human_typing",
                            },
                        )
                    await realtime_manager.publish(
                        room=room,
                        event={
                            "event": "chat.typing",
                            "channel_id": channel_id,
                            "user_id": user_id,
                            "state": state,
                        },
                    )
                continue

            if action == "chat.send":
                channel_id = payload.get("channel_id")
                content = payload.get("content")
                persona_id = payload.get("persona_id")
                mode = payload.get("mode", "single_best")

                if not isinstance(channel_id, str) or not isinstance(content, str) or not content.strip():
                    await websocket.send_json(
                        {"event": "system.error", "message": "invalid chat payload"}
                    )
                    continue

                channel = collaboration_store.get_channel(tenant_id=tenant_id, channel_id=channel_id)
                if channel is None:
                    await websocket.send_json(
                        {"event": "system.error", "message": "channel not found"}
                    )
                    continue

                org_id = str(channel.get("org_id", ""))

                if not collaboration_store.is_channel_participant(
                    tenant_id=tenant_id,
                    channel_id=channel_id,
                    user_id=user_id,
                ):
                    await websocket.send_json(
                        {"event": "system.error", "message": "channel access denied"}
                    )
                    continue

                if isinstance(persona_id, str) and persona_id:
                    selected_persona = collaboration_store.get_persona(
                        tenant_id=tenant_id,
                        persona_id=persona_id,
                    )
                    if selected_persona is None or not _is_persona_allowed_for_org(
                        tenant_id=tenant_id,
                        org_id=org_id,
                        persona=selected_persona,
                    ):
                        await websocket.send_json(
                            {
                                "event": "system.error",
                                "message": "persona not approved for current organization",
                            }
                        )
                        continue

                room = f"tenant:{tenant_id}:channel:{channel_id}"
                realtime_manager.subscribe(room=room, websocket=websocket)

                user_message = collaboration_store.create_channel_message(
                    tenant_id=tenant_id,
                    channel_id=channel_id,
                    sender_user_id=user_id,
                    content=content.strip(),
                    metadata={"sender_kind": "user"},
                )

                await realtime_manager.publish(
                    room=room,
                    event={
                        "event": "chat.message.user.created",
                        "channel_id": channel_id,
                        "message": user_message,
                    },
                )

                if mode != "single_best":
                    if mode not in {"council", "summarized", "threaded", "silent_head"}:
                        await realtime_manager.publish(
                            room=room,
                            event={
                                "event": "chat.response.skipped",
                                "channel_id": channel_id,
                                "reason": "unsupported_mode",
                            },
                        )
                        continue

                if not bool(channel.get("auto_respond", True)):
                    continue

                _cancel_pending_ai(channel_id)
                config = collaboration_store.get_room_council_config(tenant_id=tenant_id, room_id=channel_id)
                if mode in {"council", "summarized", "threaded", "silent_head"}:
                    delay_ms = (
                        int(config.get("delay_before_orchestration_ms", 10000))
                        if isinstance(config, dict)
                        else 10000
                    )
                    task = asyncio.create_task(
                        _run_council_ai(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            channel_id=channel_id,
                            requested_mode=str(mode),
                            delay_ms=delay_ms,
                        )
                    )
                else:
                    task = asyncio.create_task(
                        _run_single_best_ai(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            channel_id=channel_id,
                            persona_id=persona_id if isinstance(persona_id, str) else None,
                            delay_seconds=int(channel.get("responder_delay_seconds", 12)),
                        )
                    )
                _pending_ai_tasks[channel_id] = task
                continue

            await websocket.send_json({"event": "system.ping"})
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
