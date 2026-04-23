from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.ai_provider import generate_chat_completion
from app.core.collaboration_store import collaboration_store
from app.core.persona_prompt import compile_persona_system_prompt
from app.core.realtime_manager import realtime_manager
from app.core.security import decode_jwt
from app.core.tenant_policy import require_existing_tenant, validate_tenant_scope

router = APIRouter(tags=["realtime"])

_pending_ai_tasks: dict[str, asyncio.Task[None]] = {}


def _cancel_pending_ai(channel_id: str) -> None:
    task = _pending_ai_tasks.get(channel_id)
    if task and not task.done():
        task.cancel()


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

                if not collaboration_store.is_channel_participant(
                    tenant_id=tenant_id,
                    channel_id=channel_id,
                    user_id=user_id,
                ):
                    await websocket.send_json(
                        {"event": "system.error", "message": "channel access denied"}
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
