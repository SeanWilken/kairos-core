from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.audit_store import audit_store
from app.core.chat_action_router import resolve_chat_action
from app.core.collaboration_store import collaboration_store
from app.core.engagement_gate import evaluate_ai_engagement
from app.core.fallback_store import fallback_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.context_window_service import context_window_service
from app.core.orchestration_policy import COUNCIL_MODES, resolve_orchestration_mode
from app.core.orchestration_store import orchestration_store
from app.core.persona_prompt import compile_persona_system_prompt_resolved
from app.core.realtime_manager import realtime_manager
from app.core.security import decode_jwt
from app.core.studio_store import studio_store
from app.core.tenant_policy import require_existing_tenant, validate_tenant_scope
from app.core.tool_provider_registry import is_provider_configured

router = APIRouter(tags=["realtime"])

_pending_ai_tasks: dict[str, asyncio.Task[None]] = {}
AI_CALL_TIMEOUT_SECONDS = 45


def _cancel_pending_ai(channel_id: str) -> None:
    task = _pending_ai_tasks.get(channel_id)
    if task and not task.done():
        task.cancel()


async def _emit_room_event(
    *,
    tenant_id: str,
    channel_id: str,
    event: dict[str, Any],
    run_id: str | None = None,
) -> None:
    room = f"tenant:{tenant_id}:channel:{channel_id}"
    await realtime_manager.publish(room=room, event=event)


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
        if str(persona.get("approval_status", "")) != "approved":
            return False

    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    provider_id = str(runtime.get("provider_id", "")).strip().lower()
    if provider_id and not is_provider_configured(provider_id):
        return False

    allowlist = org_settings.get("ai_provider_allowlist", [])
    if provider_id and isinstance(allowlist, list):
        normalized = {str(item).strip().lower() for item in allowlist if str(item).strip()}
        if normalized and provider_id not in normalized:
            return False
    return True


def _persona_runtime_model_settings(persona: dict[str, Any]) -> tuple[str | None, str | None]:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    provider_id = str(runtime.get("provider_id", "")).strip().lower() or None
    model_id = str(runtime.get("model_id", "")).strip() or None
    return provider_id, model_id


def _persona_fallback_policy(persona: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(persona, dict):
        return {}
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    policy = runtime.get("fallback_policy", {})
    if isinstance(policy, dict):
        return policy
    return {}


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
    org_id: str,
    user_id: str,
    channel_id: str,
    run_id: str,
    persona: dict[str, Any],
) -> dict[str, Any]:
    messages = collaboration_store.build_conversation_messages(
        tenant_id=tenant_id,
        channel_id=channel_id,
        limit=40,
    )
    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    compaction_level = str(org_settings.get("context_compaction_level", "medium"))
    provider_override, model_override = _persona_runtime_model_settings(persona)
    persona_data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    persona_runtime = persona_data.get("runtime", {}) if isinstance(persona_data.get("runtime"), dict) else {}
    compaction_disabled = bool(persona_runtime.get("disable_compaction", False))
    context_result = context_window_service.prepare_messages(
        messages=messages,
        level=compaction_level,
        disabled=compaction_disabled,
    )
    try:
        result = await model_gateway.generate_text(
            ModelRequest(
                system_prompt=compile_persona_system_prompt_resolved(
                    tenant_id=tenant_id,
                    persona=persona,
                    org_id=org_id,
                ),
                conversation_messages=context_result.messages,
                model_profile=str(persona.get("model_profile", "reasoning-optimized")),
                provider_id=provider_override,
                model_id=model_override,
                tenant_id=tenant_id,
                org_id=org_id,
            )
        )
    except Exception as error:
        fallback_policy = _persona_fallback_policy(persona)
        fallback_provider_id = str(fallback_policy.get("provider_id", "")).strip().lower()
        fallback_model_id = str(fallback_policy.get("model_id", "")).strip()
        approval_required = bool(fallback_policy.get("approval_required", True))
        enabled = bool(fallback_policy.get("enabled", False))
        persona_id = str(persona.get("persona_id", ""))
        if enabled and approval_required and fallback_provider_id and fallback_model_id:
            consumed_approval = fallback_store.consume_approved_request(
                tenant_id=tenant_id,
                org_id=org_id,
                room_id=channel_id,
                persona_id=persona_id,
                source_provider_id=provider_override or "",
                source_model_id=model_override or "",
                fallback_provider_id=fallback_provider_id,
                fallback_model_id=fallback_model_id,
            )
            if consumed_approval is not None:
                result = await model_gateway.generate_text(
                    ModelRequest(
                        system_prompt=compile_persona_system_prompt_resolved(
                            tenant_id=tenant_id,
                            persona=persona,
                            org_id=org_id,
                        ),
                        conversation_messages=context_result.messages,
                        model_profile=str(persona.get("model_profile", "reasoning-optimized")),
                        provider_id=fallback_provider_id,
                        model_id=fallback_model_id,
                        tenant_id=tenant_id,
                        org_id=org_id,
                    )
                )
            else:
                approval_request = fallback_store.create_request(
                    tenant_id=tenant_id,
                    org_id=org_id,
                    room_id=channel_id,
                    orchestration_run_id=run_id,
                    persona_id=persona_id,
                    source_provider_id=provider_override or "",
                    source_model_id=model_override or "",
                    fallback_provider_id=fallback_provider_id,
                    fallback_model_id=fallback_model_id,
                    trigger_reason="realtime_council_generation_error",
                    created_by_user_id=user_id,
                    metadata={"error": str(error)},
                )
                audit_store.record_event(
                    tenant_id=tenant_id,
                    actor_type="user",
                    actor_id=user_id,
                    action="fallback.approval.required",
                    resource_type="fallback_approval_request",
                    resource_id=approval_request["request_id"],
                    room_id=channel_id,
                    orchestration_run_id=run_id,
                    decision="deferred",
                    reason_code="FALLBACK_APPROVAL_REQUIRED",
                )
                raise RuntimeError("fallback_approval_required") from error
        else:
            raise
    return {
        "persona_id": persona.get("persona_id"),
        "persona_name": persona.get("name"),
        "content": result.content,
        "provider": result.provider,
        "model": result.model,
        "usage": result.usage,
        "context_window": {
            "raw_token_estimate": context_result.raw_token_estimate,
            "compacted_token_estimate": context_result.compacted_token_estimate,
            "tokens_saved_estimate": context_result.tokens_saved_estimate,
            "compaction_applied": context_result.compaction_applied,
            "compaction_level": compaction_level,
            "compaction_disabled": compaction_disabled,
        },
    }


async def _run_single_best_ai(
    *,
    tenant_id: str,
    user_id: str,
    channel_id: str,
    run_id: str,
    persona_id: str | None,
    delay_seconds: int,
) -> None:
    await _emit_room_event(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        event={
            "event": "chat.response.pending",
            "channel_id": channel_id,
            "run_id": run_id,
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
            await _emit_room_event(
                tenant_id=tenant_id,
                channel_id=channel_id,
                run_id=run_id,
                event={
                    "event": "chat.response.skipped",
                    "channel_id": channel_id,
                    "run_id": run_id,
                    "reason": "persona_not_approved",
                },
            )
            orchestration_store.fail_run(run_id=run_id, reason="persona_not_approved")
            return
        system_prompt = compile_persona_system_prompt_resolved(
            tenant_id=tenant_id,
            persona=selected_persona,
            org_id=org_id,
            team_id=str(channel.get("team_id", "") or ""),
        )
        model_profile = selected_persona.get("model_profile", "reasoning-optimized")
    provider_override, model_override = _persona_runtime_model_settings(selected_persona or {})

    messages = collaboration_store.build_conversation_messages(
        tenant_id=tenant_id,
        channel_id=channel_id,
        limit=40,
    )
    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    compaction_level = str(org_settings.get("context_compaction_level", "medium"))
    persona_data = selected_persona.get("data", {}) if isinstance(selected_persona and selected_persona.get("data"), dict) else {}
    persona_runtime = persona_data.get("runtime", {}) if isinstance(persona_data.get("runtime"), dict) else {}
    compaction_disabled = bool(persona_runtime.get("disable_compaction", False))
    context_result = context_window_service.prepare_messages(
        messages=messages,
        level=compaction_level,
        disabled=compaction_disabled,
    )

    try:
        result = await asyncio.wait_for(
            model_gateway.generate_text(
                ModelRequest(
                    system_prompt=system_prompt,
                    conversation_messages=context_result.messages,
                    model_profile=model_profile,
                    provider_id=provider_override,
                    model_id=model_override,
                    tenant_id=tenant_id,
                    org_id=org_id,
                )
            ),
            timeout=AI_CALL_TIMEOUT_SECONDS,
        )
    except Exception as error:
        fallback_policy = _persona_fallback_policy(selected_persona)
        fallback_provider_id = str(fallback_policy.get("provider_id", "")).strip().lower()
        fallback_model_id = str(fallback_policy.get("model_id", "")).strip()
        approval_required = bool(fallback_policy.get("approval_required", True))
        enabled = bool(fallback_policy.get("enabled", False))
        if enabled and approval_required and fallback_provider_id and fallback_model_id:
            persona_ref = str(selected_persona.get("persona_id", "")) if isinstance(selected_persona, dict) else ""
            consumed_approval = fallback_store.consume_approved_request(
                tenant_id=tenant_id,
                org_id=org_id,
                room_id=channel_id,
                persona_id=persona_ref,
                source_provider_id=provider_override or "",
                source_model_id=model_override or "",
                fallback_provider_id=fallback_provider_id,
                fallback_model_id=fallback_model_id,
            )
            if consumed_approval is not None:
                result = await asyncio.wait_for(
                    model_gateway.generate_text(
                        ModelRequest(
                            system_prompt=system_prompt,
                            conversation_messages=context_result.messages,
                            model_profile=model_profile,
                            provider_id=fallback_provider_id,
                            model_id=fallback_model_id,
                            tenant_id=tenant_id,
                            org_id=org_id,
                        )
                    ),
                    timeout=AI_CALL_TIMEOUT_SECONDS,
                )
            else:
                approval_request = fallback_store.create_request(
                    tenant_id=tenant_id,
                    org_id=org_id,
                    room_id=channel_id,
                    orchestration_run_id=run_id,
                    persona_id=persona_ref,
                    source_provider_id=provider_override or "",
                    source_model_id=model_override or "",
                    fallback_provider_id=fallback_provider_id,
                    fallback_model_id=fallback_model_id,
                    trigger_reason="realtime_generation_error",
                    created_by_user_id=user_id,
                    metadata={"error": str(error), "mode": "single_best"},
                )
                audit_store.record_event(
                    tenant_id=tenant_id,
                    actor_type="user",
                    actor_id=user_id,
                    action="fallback.approval.required",
                    resource_type="fallback_approval_request",
                    resource_id=approval_request["request_id"],
                    room_id=channel_id,
                    orchestration_run_id=run_id,
                    decision="deferred",
                    reason_code="FALLBACK_APPROVAL_REQUIRED",
                )
                await _emit_room_event(
                    tenant_id=tenant_id,
                    channel_id=channel_id,
                    run_id=run_id,
                    event={
                        "event": "chat.response.awaiting_approval",
                        "channel_id": channel_id,
                        "run_id": run_id,
                        "request_id": approval_request["request_id"],
                    },
                )
                orchestration_store.fail_run(run_id=run_id, reason="fallback_approval_required")
                return
        await _emit_room_event(
            tenant_id=tenant_id,
            channel_id=channel_id,
            run_id=run_id,
            event={
                "event": "chat.response.failed",
                "channel_id": channel_id,
                "run_id": run_id,
                "message": str(error),
            },
        )
        orchestration_store.fail_run(run_id=run_id, reason=str(error))
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
            "context_window": {
                "raw_token_estimate": context_result.raw_token_estimate,
                "compacted_token_estimate": context_result.compacted_token_estimate,
                "tokens_saved_estimate": context_result.tokens_saved_estimate,
                "compaction_applied": context_result.compaction_applied,
                "compaction_level": compaction_level,
                "compaction_disabled": compaction_disabled,
            },
        },
    )

    await _emit_room_event(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        event={
            "event": "chat.response.completed",
            "channel_id": channel_id,
            "run_id": run_id,
            "message": assistant_message,
        },
    )
    usage = result.usage if isinstance(result.usage, dict) else {}
    input_tokens = int(usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0)
    orchestration_store.complete_run(
        run_id=run_id,
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        cost_estimate=0.0,
    )


async def _run_council_ai(
    *,
    tenant_id: str,
    user_id: str,
    channel_id: str,
    run_id: str,
    requested_mode: str,
    delay_ms: int,
) -> None:
    await _emit_room_event(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        event={
            "event": "council.delayed_start",
            "channel_id": channel_id,
            "run_id": run_id,
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
        await _emit_room_event(
            tenant_id=tenant_id,
            channel_id=channel_id,
            run_id=run_id,
            event={
                "event": "chat.response.skipped",
                "channel_id": channel_id,
                "run_id": run_id,
                "reason": "no_room_personas",
            },
        )
        orchestration_store.fail_run(run_id=run_id, reason="no_room_personas")
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

    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    max_personas = int(org_settings.get("orchestration_max_personas", 4) or 4)
    max_personas = max(1, min(max_personas, 8))
    personas = personas[:max_personas]

    if not personas:
        await _emit_room_event(
            tenant_id=tenant_id,
            channel_id=channel_id,
            run_id=run_id,
            event={
                "event": "chat.response.skipped",
                "channel_id": channel_id,
                "run_id": run_id,
                "reason": "no_approved_personas",
            },
        )
        orchestration_store.fail_run(run_id=run_id, reason="no_approved_personas")
        return

    council_mode = requested_mode
    if requested_mode == "council":
        council_mode = str(config.get("council_mode", "summarized"))
    if council_mode not in {"summarized", "threaded", "silent_head"}:
        council_mode = "summarized"

    allow_parallel = bool(config.get("allow_parallel_responses", False))
    if not bool(org_settings.get("orchestration_parallel_enabled", False)):
        allow_parallel = False

    try:
        if allow_parallel:
            responses = await asyncio.wait_for(
                asyncio.gather(
                    *[
                        _generate_persona_completion(
                            tenant_id=tenant_id,
                            org_id=org_id,
                            user_id=user_id,
                            channel_id=channel_id,
                            run_id=run_id,
                            persona=persona,
                        )
                        for persona in personas
                    ]
                ),
                timeout=AI_CALL_TIMEOUT_SECONDS,
            )
        else:
            responses: list[dict[str, Any]] = []
            for persona in personas:
                responses.append(
                        await _generate_persona_completion(
                            tenant_id=tenant_id,
                            org_id=org_id,
                            user_id=user_id,
                            channel_id=channel_id,
                            run_id=run_id,
                            persona=persona,
                        )
                )
    except Exception as error:
        responses = [
            {
                "persona_id": str(persona.get("persona_id", "")),
                "persona_name": str(persona.get("name", "persona")),
                "content": f"Council contribution unavailable: {error}",
                "provider": "system-fallback",
                "model": "fallback",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "context_window": {
                    "raw_token_estimate": 0,
                    "compacted_token_estimate": 0,
                    "tokens_saved_estimate": 0,
                    "compaction_applied": False,
                    "compaction_level": "fallback",
                    "compaction_disabled": False,
                },
            }
            for persona in personas
        ]

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
            await _emit_room_event(
                tenant_id=tenant_id,
                channel_id=channel_id,
                run_id=run_id,
                event={
                    "event": "chat.response.persona",
                    "channel_id": channel_id,
                    "run_id": run_id,
                    "message": message,
                },
            )
        orchestration_store.complete_run(run_id=run_id, usage={"input_tokens": 0, "output_tokens": 0}, cost_estimate=0.0)
        return

    if council_mode == "summarized" and len(responses) == 1:
        response = responses[0]
        summary_message = collaboration_store.create_channel_message(
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
                "mode": "summarized",
                "orchestration": "council",
                "optimization": "single_persona_skip_finalize",
            },
        )
        await _emit_room_event(
            tenant_id=tenant_id,
            channel_id=channel_id,
            run_id=run_id,
            event={
                "event": "council.response",
                "channel_id": channel_id,
                "run_id": run_id,
                "message": summary_message,
            },
        )
        orchestration_store.complete_run(run_id=run_id, usage={"input_tokens": 0, "output_tokens": 0}, cost_estimate=0.0)
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
        summary_result = await asyncio.wait_for(
            model_gateway.generate_text(
                ModelRequest(
                    system_prompt=compile_persona_system_prompt_resolved(
                        tenant_id=tenant_id,
                        persona=council_head,
                        org_id=org_id,
                        team_id=str(channel.get("team_id", "") or ""),
                    ),
                    conversation_messages=summary_messages,
                    model_profile=str(council_head.get("model_profile", "reasoning-optimized")),
                    tenant_id=tenant_id,
                    org_id=org_id,
                )
            ),
            timeout=AI_CALL_TIMEOUT_SECONDS,
        )
    except Exception:
        fallback_content = "\n".join(
            [f"- {response.get('persona_name')}: {response.get('content')}" for response in responses]
        )
        class _FallbackSummary:
            content = (
                "Council summary fallback due to generation error. "
                "Please review the collected contributions below:\n" + fallback_content
            )
            provider = "system-fallback"
            model = "fallback"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        summary_result = _FallbackSummary()

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
    await _emit_room_event(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        event={
            "event": "council.response",
            "channel_id": channel_id,
            "run_id": run_id,
            "message": summary_message,
        },
    )
    orchestration_store.complete_run(run_id=run_id, usage={"input_tokens": 0, "output_tokens": 0}, cost_estimate=0.0)


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

            try:
                if action == "subscribe":
                    room = payload.get("room")
                    if isinstance(room, str) and room.startswith(f"tenant:{tenant_id}:"):
                        realtime_manager.subscribe(room=room, websocket=websocket)
                        await websocket.send_json({"event": "system.subscribed", "room": room})
                    else:
                        await websocket.send_json({"event": "system.error", "message": "invalid room subscription"})
                    continue

                if action == "publish":
                    room = payload.get("room")
                    event = payload.get("event")
                    if isinstance(room, str) and room.startswith(f"tenant:{tenant_id}:") and isinstance(event, dict):
                        await realtime_manager.publish(room=room, event=event)
                    else:
                        await websocket.send_json({"event": "system.error", "message": "invalid publish payload"})
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
                                event={"event": "chat.response.cancelled", "channel_id": channel_id, "reason": "human_typing"},
                            )
                        await realtime_manager.publish(
                            room=room,
                            event={"event": "chat.typing", "channel_id": channel_id, "user_id": user_id, "state": state},
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

                room_personas = collaboration_store.list_room_personas(
                    tenant_id=tenant_id,
                    room_id=channel_id,
                )
                ai_handles = ["kairos", "administrator"]
                handle_to_persona_id: dict[str, str] = {}
                for room_persona in room_personas:
                    persona_id_value = str(room_persona.get("persona_id", "")).strip()
                    if not persona_id_value:
                        continue
                    persona_model = collaboration_store.get_persona(
                        tenant_id=tenant_id,
                        persona_id=persona_id_value,
                    )
                    if persona_model is None:
                        continue
                    name = str(persona_model.get("name", "")).strip()
                    slug = str(persona_model.get("slug", "")).strip()
                    if name:
                        ai_handles.append(name)
                        handle_to_persona_id["".join(ch for ch in name.lower() if ch.isalnum())] = persona_id_value
                    if slug:
                        ai_handles.append(slug)
                        handle_to_persona_id["".join(ch for ch in slug.lower() if ch.isalnum())] = persona_id_value

                engagement_mode = str(channel.get("ai_engagement_mode", "always_on"))
                settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
                org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
                decision = evaluate_ai_engagement(
                    content=content,
                    mode=engagement_mode,
                    ai_handles=ai_handles,
                )
                await realtime_manager.publish(
                    room=room,
                    event={
                        "event": "ai.engagement.evaluated",
                        "channel_id": channel_id,
                        "mode": engagement_mode,
                        "decision": decision.should_engage,
                        "reason": decision.reason,
                    },
                )
                audit_store.record_event(
                    tenant_id=tenant_id,
                    actor_type="user",
                    actor_id=user_id,
                    action="engagement.evaluated",
                    resource_type="channel",
                    resource_id=channel_id,
                    room_id=channel_id,
                    decision=("allowed" if decision.should_engage else "denied"),
                    reason_code=decision.reason,
                    metadata={"mode": engagement_mode},
                )

                if not decision.should_engage:
                    await realtime_manager.publish(
                        room=room,
                        event={
                            "event": "ai.engagement.skipped",
                            "channel_id": channel_id,
                            "reason": decision.reason,
                        },
                    )
                    continue

                room_personas = collaboration_store.list_room_personas(tenant_id=tenant_id, room_id=channel_id)
                active_persona_count = len([item for item in room_personas if bool(item.get("is_active", True))])
                action_decision = resolve_chat_action(
                    content=content,
                    requested_mode=str(mode),
                    handle_to_persona_id=handle_to_persona_id,
                    room_persona_count=active_persona_count,
                )
                if not (isinstance(persona_id, str) and persona_id.strip()) and action_decision.resolved_persona_id:
                    persona_id = action_decision.resolved_persona_id
                if action_decision.resolved_mode:
                    mode = action_decision.resolved_mode
                policy_decision = resolve_orchestration_mode(
                    requested_mode=str(mode),
                    content=content,
                    explicit_persona_selected=bool(isinstance(persona_id, str) and persona_id.strip()),
                    room_persona_count=active_persona_count,
                    auto_escalation_enabled=bool(org_settings.get("orchestration_auto_escalation_enabled", True)),
                )
                mode = policy_decision.effective_mode
                await _emit_room_event(
                    tenant_id=tenant_id,
                    channel_id=channel_id,
                    event={
                        "event": "orchestration.policy.resolved",
                        "channel_id": channel_id,
                        "requested_mode": policy_decision.requested_mode,
                        "effective_mode": policy_decision.effective_mode,
                        "reason": policy_decision.reason,
                        "action_type": action_decision.action_type,
                        "action_reason": action_decision.reason,
                        "resolved_persona_id": persona_id if isinstance(persona_id, str) else None,
                        "estimated_calls_min": policy_decision.estimated_calls_min,
                    },
                )

                client_message_id = str(payload.get("client_message_id", "")).strip()
                idempotency_key = str(payload.get("idempotency_key", "")).strip()
                existing_run = orchestration_store.get_run_by_idempotency(
                    tenant_id=tenant_id,
                    room_id=channel_id,
                    created_by_user_id=user_id,
                    idempotency_key=idempotency_key,
                )
                if existing_run is not None:
                    existing_run_id = str(existing_run.get("run_id", ""))
                    await _emit_room_event(
                        tenant_id=tenant_id,
                        channel_id=channel_id,
                        run_id=existing_run_id or None,
                        event={
                            "event": "orchestration.run.replay_attached",
                            "channel_id": channel_id,
                            "run_id": existing_run_id,
                            "status": existing_run.get("status"),
                        },
                    )
                    continue

                run = orchestration_store.create_run(
                    tenant_id=tenant_id,
                    room_id=channel_id,
                    triggering_message_id=str(user_message.get("message_id", "")) or None,
                    created_by_user_id=user_id,
                    orchestration_type=("council" if mode in COUNCIL_MODES else "single_best"),
                    mode=str(mode),
                    client_message_id=client_message_id,
                    idempotency_key=idempotency_key,
                )
                run_id = str(run.get("run_id", ""))
                audit_store.record_event(
                    tenant_id=tenant_id,
                    actor_type="user",
                    actor_id=user_id,
                    action="orchestration.run.created",
                    resource_type="orchestration_run",
                    resource_id=run_id,
                    room_id=channel_id,
                    orchestration_run_id=run_id,
                    metadata={"mode": mode},
                )
                orchestration_store.add_outbox_event(
                    tenant_id=tenant_id,
                    room_id=channel_id,
                    orchestration_run_id=run_id,
                    event_type="orchestration.run.created",
                    payload={
                        "run_id": run_id,
                        "channel_id": channel_id,
                        "mode": mode,
                        "orchestration_type": run.get("orchestration_type"),
                    },
                )
                await realtime_manager.publish(
                    room=room,
                    event={
                        "event": "orchestration.run.created",
                        "channel_id": channel_id,
                        "run_id": run_id,
                        "mode": mode,
                    },
                )

                if mode != "single_best":
                    if mode not in COUNCIL_MODES:
                        await realtime_manager.publish(
                            room=room,
                            event={
                                "event": "chat.response.skipped",
                                "channel_id": channel_id,
                                "run_id": run_id,
                                "reason": "unsupported_mode",
                            },
                        )
                        orchestration_store.fail_run(run_id=run_id, reason="unsupported_mode")
                        continue

                if not bool(channel.get("auto_respond", True)):
                    continue

                _cancel_pending_ai(channel_id)
                config = collaboration_store.get_room_council_config(tenant_id=tenant_id, room_id=channel_id)
                if mode in COUNCIL_MODES:
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
                            run_id=run_id,
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
                            run_id=run_id,
                            persona_id=persona_id if isinstance(persona_id, str) else None,
                            delay_seconds=int(channel.get("responder_delay_seconds", 12)),
                        )
                    )
                    _pending_ai_tasks[channel_id] = task
                    continue

                await websocket.send_json({"event": "system.ping"})
            except Exception as error:
                await websocket.send_json({"event": "system.error", "message": f"processing_error:{error}"})
                continue
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
