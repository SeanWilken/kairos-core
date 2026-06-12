from __future__ import annotations

import re
import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.audit_store import audit_store
from app.core.chat_action_router import resolve_chat_action
from app.core.chat_contracts import normalize_chat_controls
from app.core.collaboration_store import collaboration_store
from app.core.engagement_gate import evaluate_ai_engagement
from app.core.fallback_store import fallback_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.context_window_service import context_window_service
from app.core.orchestration_policy import COUNCIL_MODES, resolve_orchestration_mode
from app.core.orchestration_store import orchestration_store
from app.core.persona_prompt import compile_persona_system_prompt_resolved
from app.core.prompt_template_runtime import resolve_rendered_prompt_template
from app.core.realtime_manager import realtime_manager
from app.core.security import decode_jwt
from app.core.studio_store import studio_store
from app.core.tool_execution_store import tool_execution_store
from app.core.tool_runtime import generate_image_tool
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


async def _emit_response_blocks(
    *,
    tenant_id: str,
    channel_id: str,
    message: dict[str, Any],
    run_id: str | None = None,
) -> None:
    metadata = message.get("metadata", {}) if isinstance(message.get("metadata"), dict) else {}
    structured = metadata.get("structured_content", {}) if isinstance(metadata.get("structured_content"), dict) else {}
    blocks = structured.get("blocks", []) if isinstance(structured.get("blocks"), list) else []
    message_id = str(message.get("message_id", "")).strip()
    if not message_id or not blocks:
        return

    await _emit_room_event(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        event={
            "event": "chat.response.started",
            "channel_id": channel_id,
            "run_id": run_id,
            "response_id": message_id,
            "message_id": message_id,
            "block_count": len(blocks),
            "primary_type": structured.get("primary_type", "text"),
            "render_hint": structured.get("render_hint", "plain_text"),
            "response_type": metadata.get("response_type", structured.get("response_type", "conversation")),
            "orchestration": metadata.get("orchestration", "single_best"),
        },
    )

    for index, block in enumerate(blocks):
        block_payload = dict(block) if isinstance(block, dict) else {"type": "text", "text": str(block)}
        block_type = str(block_payload.get("type", "text")).strip().lower()
        block_id = str(block_payload.get("block_id", f"block:{index}")).strip() or f"block:{index}"
        block_payload["block_id"] = block_id
        await _emit_room_event(
            tenant_id=tenant_id,
            channel_id=channel_id,
            run_id=run_id,
            event={
                "event": "chat.response.block",
                "channel_id": channel_id,
                "run_id": run_id,
                "response_id": message_id,
                "message_id": message_id,
                "sequence": index,
                "block_type": block_type,
                "orchestration": metadata.get("orchestration", "single_best"),
                "block": block_payload,
            },
        )


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


def _persona_provider_id(persona: dict[str, Any]) -> str:
    provider_id, _ = _persona_runtime_model_settings(persona)
    return provider_id or "openai"


def _append_prompt(base: str, extension: str) -> str:
    left = str(base or "").strip()
    right = str(extension or "").strip()
    if not right:
        return left
    if not left:
        return right
    return f"{left}\n\n{right}"


def _workflow_template_kind(message_content: str) -> str:
    lowered = str(message_content or "").strip().lower()
    if lowered.startswith("/focus"):
        return "focus_group_prompt"
    if lowered.startswith("/flow") or lowered.startswith("/agent"):
        return "tasking_prompt"
    return "planner_prompt"


def _persona_access_level(persona: dict[str, Any]) -> str:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    access = data.get("access_policy", {}) if isinstance(data.get("access_policy"), dict) else {}
    level = str(access.get("visibility", "organization")).strip().lower()
    return level or "organization"


def _can_access_persona_for_roles(*, roles: list[str], is_global_admin: bool, persona: dict[str, Any]) -> bool:
    level = _persona_access_level(persona)
    if level in {"admin_only", "restricted_admin"}:
        return bool(is_global_admin or any(role in {"owner", "admin", "global_admin"} for role in roles))
    return True


def _response_type_instruction(response_type: str) -> str:
    kind = str(response_type or "conversation").strip().lower()
    if kind == "markdown":
        return "Return well-structured markdown with headings, short lists, and code fences when useful."
    if kind == "summary":
        return "Return a concise executive summary with key decisions, risks, and next actions."
    if kind == "reporting":
        return (
            "Return a reporting-oriented response with sections for findings, metrics, assumptions, "
            "and tabular data where possible."
        )
    return "Return a natural conversational response."


def _parse_image_command(content: str) -> str:
    text = str(content or "").strip()
    if not text.lower().startswith("/image"):
        return ""
    parts = text.split(" ", 1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _infer_image_prompt(content: str) -> str:
    text = str(content or "").strip()
    lowered = text.lower()
    if lowered.startswith("/image"):
        return _parse_image_command(text)
    triggers = ["create an image", "generate an image", "hero image", "mockup", "visual concept"]
    if any(token in lowered for token in triggers):
        return text
    return ""


def _build_structured_content(
    *,
    text: str,
    response_type: str,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    kind = str(response_type or "conversation").strip().lower()
    blocks = _segment_structured_blocks(text=text, response_type=kind)
    block_types = [str(block.get("type", "")).strip().lower() for block in blocks if isinstance(block, dict)]
    unique_non_image_types = [item for item in block_types if item and item != "image"]
    unique_non_image_types = list(dict.fromkeys(unique_non_image_types))
    if not unique_non_image_types:
        primary_type = "markdown" if kind in {"markdown", "summary", "reporting"} else "text"
    elif len(unique_non_image_types) == 1:
        primary_type = unique_non_image_types[0]
    else:
        primary_type = "mixed"
    for item in attachments or []:
        if str(item.get("type", "")).strip().lower() != "image":
            continue
        blocks.append(
            {
                "type": "image",
                "url": str(item.get("asset_url", "")),
                "alt": "Generated image",
                "caption": str(item.get("status", "")),
                "mime_type": str(item.get("mime_type", "image/png")),
                "image_base64": str(item.get("image_base64", "")),
            }
        )
    return {
        "version": "v1",
        "primary_type": primary_type,
        "response_type": kind,
        "render_hint": (
            "markdown"
            if primary_type == "markdown"
            else "structured_blocks" if primary_type == "mixed" else "plain_text"
        ),
        "blocks": blocks,
    }


def _build_content_block(*, kind: str, body: str, index: int) -> dict[str, Any]:
    block_id = f"block:{index}"
    capabilities = {
        "replyable": True,
        "editable": kind == "markdown",
        "saveable": kind in {"markdown", "text", "code"},
        "copyable": True,
    }
    if kind == "markdown":
        return {
            "block_id": block_id,
            "type": "markdown",
            "markdown": body,
            "capabilities": capabilities,
        }
    return {
        "block_id": block_id,
        "type": "text",
        "text": body,
        "capabilities": capabilities,
    }


def _split_mixed_blocks(text: str) -> list[dict[str, Any]]:
    content = str(text or "").replace("\r\n", "\n")
    if not content.strip():
        return [{"type": "text", "text": ""}]

    lines = content.split("\n")
    segments: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_kind: str | None = None
    in_code_block = False

    def flush() -> None:
        nonlocal current_lines, current_kind
        if not current_lines:
            current_kind = None
            return
        body = "\n".join(current_lines).strip("\n")
        if body:
            segments.append((current_kind or "text", body))
        current_lines = []
        current_kind = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code_block:
                flush()
                in_code_block = True
                current_kind = "markdown"
                current_lines = [line]
            else:
                current_lines.append(line)
                flush()
                in_code_block = False
            continue
        if in_code_block:
            current_lines.append(line)
            continue
        if not stripped:
            flush()
            continue
        line_kind = "markdown" if _looks_like_markdown_line(stripped) else "text"
        if current_kind is None:
            current_kind = line_kind
            current_lines = [line]
            continue
        if line_kind != current_kind:
            flush()
            current_kind = line_kind
            current_lines = [line]
            continue
        current_lines.append(line)

    flush()

    if not segments:
        return [{"type": "text", "text": content}]

    blocks: list[dict[str, Any]] = []
    for index, (kind, body) in enumerate(segments):
        blocks.append(_build_content_block(kind=kind, body=body, index=index))
    return blocks


def _segment_structured_blocks(*, text: str, response_type: str) -> list[dict[str, Any]]:
    content = str(text or "").replace("\r\n", "\n")
    if not content.strip():
        return [{"type": "text", "text": ""}]
    blocks = _split_mixed_blocks(content)
    kind = str(response_type or "").strip().lower()
    if kind in {"markdown", "summary", "reporting"}:
        non_image_blocks = [block for block in blocks if str(block.get("type", "")).strip().lower() != "image"]
        if non_image_blocks and all(str(block.get("type", "")).strip().lower() == "text" for block in non_image_blocks):
            return [_build_content_block(kind="markdown", body=content, index=0)]
    return blocks


def _looks_like_markdown_line(line: str) -> bool:
    if re.match(r"^#{1,6}\s", line):
        return True
    if re.match(r"^[-*+]\s", line):
        return True
    if re.match(r"^\d+\.\s", line):
        return True
    if re.match(r"^>\s", line):
        return True
    if re.match(r"^[-*_]{3,}$", line):
        return True
    if line.startswith("|") and line.endswith("|"):
        return True
    return False


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
    action_type: str = "general",
    message_content: str = "",
    response_type: str = "conversation",
    planning_notes: str = "",
    participant_control: dict[str, Any] | None = None,
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
    control = participant_control if isinstance(participant_control, dict) else {}
    override_provider = str(control.get("runtime_provider_id", "")).strip().lower()
    override_model = str(control.get("runtime_model_id", "")).strip()
    if override_provider and is_provider_configured(override_provider):
        provider_override = override_provider
    if override_model:
        model_override = override_model
    effective_response_type = str(control.get("response_type", "")).strip().lower() or response_type
    persona_data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    persona_runtime = persona_data.get("runtime", {}) if isinstance(persona_data.get("runtime"), dict) else {}
    compaction_disabled = bool(persona_runtime.get("disable_compaction", False))
    context_result = context_window_service.prepare_messages(
        messages=messages,
        level=compaction_level,
        disabled=compaction_disabled,
    )
    try:
        base_system_prompt = compile_persona_system_prompt_resolved(
            tenant_id=tenant_id,
            persona=persona,
            org_id=org_id,
        )
        provider_id = _persona_provider_id(persona)
        template_kind = "tool_call_prompt"
        if action_type == "workflow":
            template_kind = _workflow_template_kind(message_content)
        prompt_extension = resolve_rendered_prompt_template(
            tenant_id=tenant_id,
            provider_id=provider_id,
            template_kind=template_kind,
            scopes={"team": "", "division": "", "org": org_id, "tenant": tenant_id},
            context={
                "persona": {
                    "name": persona.get("name", ""),
                    "role": persona.get("role", ""),
                    "scope": persona.get("scope", "organization"),
                },
                "request": {"message": message_content, "action_type": action_type},
            },
        )
        if planning_notes.strip():
            prompt_extension = _append_prompt(
                prompt_extension,
                "Planner notes for this turn: " + planning_notes.strip(),
            )
        effective_system_prompt = _append_prompt(base_system_prompt, prompt_extension)
        effective_system_prompt = _append_prompt(effective_system_prompt, _response_type_instruction(effective_response_type))
        result = await model_gateway.generate_text(
            ModelRequest(
                system_prompt=effective_system_prompt,
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
                        system_prompt=effective_system_prompt,
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
        "applied_controls": {
            "response_type": effective_response_type,
            "runtime_provider_id": provider_override or "",
            "runtime_model_id": model_override or "",
        },
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
    response_type: str = "conversation",
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

    system_prompt = _append_prompt(system_prompt, _response_type_instruction(response_type))

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
            "structured_content": _build_structured_content(text=result.content, response_type=response_type),
        },
    )

    await _emit_response_blocks(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        message=assistant_message,
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
    action_type: str = "general",
    message_content: str = "",
    response_type: str = "conversation",
    participant_controls: dict[str, dict[str, Any]] | None = None,
    explicit_persona_calls: list[str] | None = None,
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

    calls = [str(item).strip() for item in (explicit_persona_calls or []) if str(item).strip()]
    if calls:
        allowed_ids = set(calls)
        personas = [item for item in personas if str(item.get("persona_id", "")) in allowed_ids]

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

    controls = participant_controls if isinstance(participant_controls, dict) else {}
    applied_control_map: dict[str, dict[str, Any]] = {}
    for persona in personas:
        persona_id = str(persona.get("persona_id", "")).strip()
        if not persona_id:
            continue
        control = controls.get(persona_id, {}) if isinstance(controls.get(persona_id, {}), dict) else {}
        applied_control_map[persona_id] = {
            "response_type": str(control.get("response_type", "")).strip().lower() or response_type,
            "runtime_provider_id": str(control.get("runtime_provider_id", "")).strip().lower(),
            "runtime_model_id": str(control.get("runtime_model_id", "")).strip(),
        }

    await _emit_room_event(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        event={
            "event": "orchestration.controls.applied",
            "channel_id": channel_id,
            "run_id": run_id,
            "chat_type": "group",
            "explicit_persona_calls": calls,
            "global_response_type": response_type,
            "participant_controls": applied_control_map,
        },
    )

    council_mode = requested_mode
    if requested_mode == "council":
        council_mode = str(config.get("council_mode", "summarized"))
    if council_mode not in {"summarized", "threaded", "silent_head"}:
        council_mode = "summarized"

    allow_parallel = bool(config.get("allow_parallel_responses", False))
    if not bool(org_settings.get("orchestration_parallel_enabled", False)):
        allow_parallel = False

    planning_notes = ""
    if action_type == "workflow":
        planner_persona = personas[0]
        planner_messages = [
            {
                "role": "user",
                "content": (
                    "Create a concise execution plan for collaborating personas. "
                    "Include goals, role assignments, and expected deliverable format.\n\n"
                    f"User request: {message_content}"
                ),
            }
        ]
        planner_prompt = resolve_rendered_prompt_template(
            tenant_id=tenant_id,
            provider_id=_persona_provider_id(planner_persona),
            template_kind="planner_prompt",
            scopes={"team": str(channel.get("team_id", "") or ""), "division": "", "org": org_id, "tenant": tenant_id},
            context={
                "persona": {
                    "name": planner_persona.get("name", ""),
                    "role": planner_persona.get("role", ""),
                    "scope": planner_persona.get("scope", "organization"),
                },
                "request": {"message": message_content, "action_type": action_type},
            },
        )
        try:
            planner_result = await model_gateway.generate_text(
                ModelRequest(
                    system_prompt=_append_prompt(
                        compile_persona_system_prompt_resolved(
                            tenant_id=tenant_id,
                            persona=planner_persona,
                            org_id=org_id,
                            team_id=str(channel.get("team_id", "") or ""),
                        ),
                        planner_prompt,
                    ),
                    conversation_messages=planner_messages,
                    model_profile=str(planner_persona.get("model_profile", "reasoning-optimized")),
                    tenant_id=tenant_id,
                    org_id=org_id,
                )
            )
            planning_notes = str(planner_result.content or "").strip()
            await _emit_room_event(
                tenant_id=tenant_id,
                channel_id=channel_id,
                run_id=run_id,
                event={
                    "event": "orchestration.plan.generated",
                    "channel_id": channel_id,
                    "run_id": run_id,
                    "planner_persona_id": planner_persona.get("persona_id"),
                    "plan": planning_notes,
                },
            )
        except Exception:
            planning_notes = ""

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
                            action_type=action_type,
                            message_content=message_content,
                            response_type=response_type,
                            planning_notes=planning_notes,
                            participant_control=controls.get(str(persona.get("persona_id", "")), {}),
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
                            action_type=action_type,
                            message_content=message_content,
                            response_type=response_type,
                            planning_notes=planning_notes,
                            participant_control=controls.get(str(persona.get("persona_id", "")), {}),
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
                    "structured_content": _build_structured_content(text=response["content"], response_type=response_type),
                },
            )
            await _emit_response_blocks(
                tenant_id=tenant_id,
                channel_id=channel_id,
                run_id=run_id,
                message=message,
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
                "structured_content": _build_structured_content(text=response["content"], response_type=response_type),
            },
        )
        await _emit_response_blocks(
            tenant_id=tenant_id,
            channel_id=channel_id,
            run_id=run_id,
            message=summary_message,
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

    council_head_provider = _persona_provider_id(council_head)
    planner_extension = resolve_rendered_prompt_template(
        tenant_id=tenant_id,
        provider_id=council_head_provider,
        template_kind=("planner_prompt" if action_type == "workflow" else "system_prompt"),
        scopes={
            "team": str(channel.get("team_id", "") or ""),
            "division": "",
            "org": org_id,
            "tenant": tenant_id,
        },
        context={
            "persona": {
                "name": council_head.get("name", ""),
                "role": council_head.get("role", ""),
                "scope": council_head.get("scope", "organization"),
            },
            "request": {"message": message_content, "action_type": action_type},
            "council": {"response_count": len(responses)},
        },
    )

    summary_system_prompt = compile_persona_system_prompt_resolved(
        tenant_id=tenant_id,
        persona=council_head,
        org_id=org_id,
        team_id=str(channel.get("team_id", "") or ""),
    )
    if planner_extension:
        summary_system_prompt = _append_prompt(summary_system_prompt, planner_extension)
    summary_system_prompt = _append_prompt(summary_system_prompt, _response_type_instruction(response_type))

    try:
        summary_result = await asyncio.wait_for(
            model_gateway.generate_text(
                ModelRequest(
                    system_prompt=summary_system_prompt,
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
            "structured_content": _build_structured_content(text=summary_result.content, response_type=response_type),
        },
    )
    await _emit_response_blocks(
        tenant_id=tenant_id,
        channel_id=channel_id,
        run_id=run_id,
        message=summary_message,
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
    roles_claim = claims.get("roles")
    roles = [str(item) for item in roles_claim] if isinstance(roles_claim, list) else []
    is_global_admin = bool(claims.get("is_global_admin", False))
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
                    normalized_controls = normalize_chat_controls(payload if isinstance(payload, dict) else {})
                    if not bool(normalized_controls.get("accepted", False)):
                        await websocket.send_json(
                            {
                                "event": "system.error",
                                "message": "chat_payload_validation_failed",
                                "details": {
                                    "reason_code": "CHAT_PAYLOAD_VALIDATION_FAILED",
                                    "rejections": normalized_controls.get("rejections", []),
                                    "warnings": normalized_controls.get("warnings", []),
                                },
                            }
                        )
                        continue
                    normalized = (
                        normalized_controls.get("normalized", {})
                        if isinstance(normalized_controls.get("normalized"), dict)
                        else {}
                    )
                    channel_id = payload.get("channel_id")
                    content = normalized.get("content", payload.get("content"))
                    persona_id = normalized.get("persona_id")
                    mode = normalized.get("mode", payload.get("mode", "single_best"))
                    response_type = str(normalized.get("response_type", payload.get("response_type", "conversation")))
                    participant_controls = (
                        normalized.get("participant_controls", {})
                        if isinstance(normalized.get("participant_controls", {}), dict)
                        else {}
                    )
                    explicit_persona_calls = (
                        normalized.get("explicit_persona_calls", [])
                        if isinstance(normalized.get("explicit_persona_calls", []), list)
                        else []
                    )

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
                        if not _can_access_persona_for_roles(
                            roles=roles,
                            is_global_admin=is_global_admin,
                            persona=selected_persona,
                        ):
                            await websocket.send_json(
                                {
                                    "event": "system.error",
                                    "message": "persona access denied",
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
                        metadata={
                            "sender_kind": "user",
                            "structured_content": {
                                "version": "v1",
                                "blocks": normalized.get("content_blocks", []),
                            }
                            if normalized.get("content_blocks")
                            else {"version": "v1", "blocks": [{"type": "text", "text": content.strip()}]},
                        },
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
                ai_handles = ["myai", "administrator"]
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

                image_prompt = _infer_image_prompt(content)
                if image_prompt:
                    provider_id = "google"
                    model_id = "imagen-3.0-generate-002"
                    if isinstance(persona_id, str) and persona_id.strip():
                        selected_persona = collaboration_store.get_persona(
                            tenant_id=tenant_id,
                            persona_id=persona_id,
                        )
                        if isinstance(selected_persona, dict):
                            if not _can_access_persona_for_roles(
                                roles=roles,
                                is_global_admin=is_global_admin,
                                persona=selected_persona,
                            ):
                                await websocket.send_json(
                                    {
                                        "event": "system.error",
                                        "message": "persona access denied",
                                    }
                                )
                                continue
                            runtime_provider, runtime_model = _persona_runtime_model_settings(selected_persona)
                            if runtime_provider in {"google", "openai"}:
                                provider_id = runtime_provider
                            if runtime_model:
                                model_id = runtime_model

                    auto_execute = bool(normalized.get("auto_execute_tools", True))
                    if auto_execute:
                        tool_output = generate_image_tool(
                            prompt=image_prompt,
                            provider_id=provider_id,
                            model_id=model_id,
                        )
                        execution = tool_execution_store.create_execution(
                            tenant_id=tenant_id,
                            org_id=org_id,
                            tool_id="nano_banana",
                            provider_id=str(tool_output.get("provider_id", provider_id)),
                            model_id=str(tool_output.get("model_id", model_id)),
                            input_payload={"prompt": image_prompt},
                            output_payload=tool_output,
                            created_by_user_id=user_id,
                            status=str(tool_output.get("status", "completed")),
                        )
                    else:
                        tool_output = {
                            "provider_id": provider_id,
                            "model_id": model_id,
                            "mime_type": "image/png",
                            "status": "recommended",
                            "note": "Tool call was recommended but not executed.",
                        }
                        execution = {"execution_id": "", "provider_id": provider_id, "model_id": model_id}
                    assistant_message = collaboration_store.create_channel_message(
                        tenant_id=tenant_id,
                        channel_id=channel_id,
                        sender_user_id=user_id,
                        content=("Generated image from prompt." if auto_execute else "Image recommendation prepared."),
                        metadata={
                            "sender_kind": "assistant",
                            "mode": "single_best",
                            "tool_call": {
                                "tool_id": "nano_banana",
                                "execution_id": execution.get("execution_id"),
                                "provider": execution.get("provider_id"),
                                "model": execution.get("model_id"),
                            },
                            "attachments": [
                                {
                                    "type": "image",
                                    "mime_type": str(tool_output.get("mime_type", "image/png")),
                                    "asset_url": str(tool_output.get("asset_url", "")),
                                    "image_base64": str(tool_output.get("image_base64", "")),
                                    "status": str(tool_output.get("status", "")),
                                }
                            ],
                            "structured_content": _build_structured_content(
                                text=("Generated image from prompt." if auto_execute else "Image recommendation prepared."),
                                response_type=response_type,
                                attachments=[
                                    {
                                        "type": "image",
                                        "mime_type": str(tool_output.get("mime_type", "image/png")),
                                        "asset_url": str(tool_output.get("asset_url", "")),
                                        "image_base64": str(tool_output.get("image_base64", "")),
                                        "status": str(tool_output.get("status", "")),
                                    }
                                ],
                            ),
                        },
                    )
                    await _emit_response_blocks(
                        tenant_id=tenant_id,
                        channel_id=channel_id,
                        message=assistant_message,
                    )
                    await realtime_manager.publish(
                        room=room,
                        event={
                            "event": "chat.response.completed",
                            "channel_id": channel_id,
                            "message": assistant_message,
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
                            action_type=action_decision.action_type,
                            message_content=content,
                            response_type=response_type,
                            participant_controls=participant_controls,
                            explicit_persona_calls=explicit_persona_calls,
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
                            response_type=response_type,
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
