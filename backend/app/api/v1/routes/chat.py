from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.audit_store import audit_store
from app.core.auth_context import AuthContext, require_authentication, require_roles
from app.core.chat_contracts import normalize_chat_controls
from app.core.collaboration_store import collaboration_store
from app.core.context_window_service import context_window_service
from app.core.fallback_store import fallback_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.persona_prompt import compile_persona_system_prompt, compile_persona_system_prompt_resolved
from app.core.prompt_template_runtime import resolve_rendered_prompt_template
from app.core.resume_export_adapter import build_provider_resume_export
from app.core.resume_adapter_policy_store import resume_adapter_policy_store
from app.core.response import ok_response
from app.core.studio_store import studio_store
from app.core.tool_execution_store import tool_execution_store
from app.core.tool_runtime import generate_image_tool
from app.core.tool_provider_registry import get_ai_provider_catalog, is_provider_configured

router = APIRouter(prefix="/studio", tags=["studio-chat"])


class PersonaCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    role: str = Field(min_length=1)
    scope: str = Field(default="organization")
    enabled: bool = True
    model_profile: str = Field(default="reasoning-optimized")
    runtime_provider_id: str | None = None
    runtime_model_id: str | None = None
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class PersonaPatchPayload(BaseModel):
    name: str | None = None
    slug: str | None = None
    role: str | None = None
    scope: str | None = None
    enabled: bool | None = None
    model_profile: str | None = None
    runtime_provider_id: str | None = None
    runtime_model_id: str | None = None
    fallback_policy: dict[str, Any] | None = None
    system_prompt: str | None = None
    data: dict[str, Any] | None = None
    version_bump: str = Field(default="patch")
    change_summary: str = ""


class PersonaApprovalPayload(BaseModel):
    approved: bool = True


class RoomCouncilConfigPayload(BaseModel):
    council_head_persona_id: str | None = None
    council_mode: str = Field(default="summarized")
    delay_before_orchestration_ms: int = Field(default=10000, ge=0, le=120000)
    show_reasoning_metadata: bool = True
    allow_parallel_responses: bool = False


class RoomPersonaItemPayload(BaseModel):
    persona_id: str = Field(min_length=1)
    role_in_room: str = Field(default="member")
    sort_order: int = 0
    is_active: bool = True


class RoomPersonasPayload(BaseModel):
    personas: list[RoomPersonaItemPayload] = Field(default_factory=list)


class UserPersonaContextPayload(BaseModel):
    user_strengths: list[str] = Field(default_factory=list)
    user_weaknesses: list[str] = Field(default_factory=list)
    autonomy_level: str = "moderate"
    communication_preference: str = "balanced"
    detail_level: str = "standard"
    check_in_frequency: str = "as_needed"
    context: dict[str, Any] = Field(default_factory=dict)


class ChannelPolicyPatchPayload(BaseModel):
    response_policy: str | None = None
    auto_respond: bool | None = None
    responder_delay_seconds: int | None = Field(default=None, ge=0, le=120)
    default_persona_id: str | None = None


class ChannelChatPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: str = Field(min_length=1)
    persona_id: str | None = None
    mode: str = Field(default="single_best")
    response_type: str = Field(default="conversation")
    chat_type: str = Field(default="one_to_one")
    global_controls: dict[str, Any] = Field(default_factory=dict)
    participant_controls: dict[str, dict[str, Any]] = Field(default_factory=dict)
    persona_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    explicit_persona_calls: list[str] = Field(default_factory=list)
    auto_execute_tools: bool = True
    strict_validation: bool = False


def _enforce_org_scope(auth: AuthContext, org_id: str) -> None:
    if auth.is_global_admin:
        return
    if not auth.org_id or auth.org_id != org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Operation is outside current organization scope.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )


def _can_manage_channel(auth: AuthContext, channel: dict[str, Any]) -> bool:
    if auth.is_global_admin:
        return True
    if channel.get("created_by_user_id") == auth.user_id:
        return True
    return any(role in {"owner", "admin"} for role in auth.roles)


def _enforce_persona_policy(
    *,
    tenant_id: str,
    org_id: str,
    persona: dict[str, Any] | None,
) -> None:
    if persona is None:
        return
    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    mode = str(org_settings.get("prompt_policy_mode", "open"))
    if mode in {"approval_required", "allowlist_only"} and persona.get("approval_status") != "approved":
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona is not approved for current organization prompt policy.",
                "details": {"reason_code": "STUDIO_PERSONA_APPROVAL_REQUIRED", "prompt_policy_mode": mode},
            },
        )

    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    provider_id = str(runtime.get("provider_id", "")).strip().lower()
    if provider_id and not is_provider_configured(provider_id):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona provider is not configured for this deployment.",
                "details": {"reason_code": "STUDIO_PERSONA_PROVIDER_UNAVAILABLE", "provider_id": provider_id},
            },
        )

    allowed_providers = org_settings.get("ai_provider_allowlist", [])
    if isinstance(allowed_providers, list) and provider_id:
        normalized = {str(item).strip().lower() for item in allowed_providers if str(item).strip()}
        if normalized and provider_id not in normalized:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Persona provider is not allowed in this organization.",
                    "details": {"reason_code": "STUDIO_PERSONA_PROVIDER_FORBIDDEN", "provider_id": provider_id},
                },
            )


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


def _append_prompt(base: str, extension: str) -> str:
    left = str(base or "").strip()
    right = str(extension or "").strip()
    if not right:
        return left
    if not left:
        return right
    return f"{left}\n\n{right}"


def _parse_image_command(content: str) -> str:
    text = str(content or "").strip()
    if not text.lower().startswith("/image"):
        return ""
    parts = text.split(" ", 1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


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


def _persona_access_level(persona: dict[str, Any]) -> str:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    access = data.get("access_policy", {}) if isinstance(data.get("access_policy"), dict) else {}
    level = str(access.get("visibility", "organization")).strip().lower()
    return level or "organization"


def _can_access_persona(*, auth: AuthContext, persona: dict[str, Any]) -> bool:
    level = _persona_access_level(persona)
    if level in {"admin_only", "restricted_admin"}:
        return bool(auth.is_global_admin or any(role in {"owner", "admin"} for role in auth.roles))
    return True


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


def _split_mixed_blocks(text: str) -> list[dict[str, Any]]:
    lines = text.split("\n")
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
        return [{"type": "text", "text": text}]

    blocks: list[dict[str, Any]] = []
    for index, (kind, body) in enumerate(segments):
        blocks.append(_build_content_block(kind=kind, body=body, index=index))
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


def _build_chat_options(
    *,
    tenant_id: str,
    org_id: str,
    channel_id: str,
    selected_persona_id: str | None,
) -> dict[str, Any]:
    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    room_personas = collaboration_store.list_room_personas(tenant_id=tenant_id, room_id=channel_id)
    participant_options: list[dict[str, Any]] = []
    for room_persona in room_personas:
        persona_id = str(room_persona.get("persona_id", "")).strip()
        if not persona_id:
            continue
        persona = collaboration_store.get_persona(tenant_id=tenant_id, persona_id=persona_id)
        if persona is None:
            continue
        provider_id, model_id = _persona_runtime_model_settings(persona)
        participant_options.append(
            {
                "persona_id": persona_id,
                "name": persona.get("name", ""),
                "role_in_room": room_persona.get("role_in_room", "member"),
                "model_profile": persona.get("model_profile", "reasoning-optimized"),
                "runtime_provider_id": provider_id or "",
                "runtime_model_id": model_id or "",
                "response_types": ["conversation", "markdown", "summary", "reporting"],
                "modes": ["single_best", "council", "summarized", "threaded", "silent_head"],
            }
        )

    return {
        "administrator_default_persona_id": selected_persona_id,
        "response_types": ["conversation", "markdown", "summary", "reporting"],
        "modes": ["single_best", "council", "summarized", "threaded", "silent_head"],
        "workflow_actions": ["general", "focus_group", "tasking", "agent"],
        "prompt_template_kinds": [
            "system_prompt",
            "planner_prompt",
            "tool_call_prompt",
            "focus_group_prompt",
            "tasking_prompt",
            "reflection_prompt",
        ],
        "parallel_enabled": bool(org_settings.get("orchestration_parallel_enabled", False)),
        "max_personas": int(org_settings.get("orchestration_max_personas", 4) or 4),
        "participant_options": participant_options,
    }


def _merge_persona_runtime(
    *,
    base_data: dict[str, Any],
    runtime_provider_id: str | None,
    runtime_model_id: str | None,
    fallback_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    data = dict(base_data)
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    if runtime_provider_id is not None:
        runtime["provider_id"] = runtime_provider_id.strip().lower()
    if runtime_model_id is not None:
        runtime["model_id"] = runtime_model_id.strip()
    if fallback_policy is not None:
        runtime["fallback_policy"] = fallback_policy
    data["runtime"] = runtime
    return data


def _persona_voice_profile(persona: dict[str, Any]) -> dict[str, Any]:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    voice = data.get("voice", {}) if isinstance(data.get("voice"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    runtime_voice = runtime.get("voice", {}) if isinstance(runtime.get("voice"), dict) else {}
    return {**runtime_voice, **voice}


def _validate_runtime_provider(*, tenant_id: str, org_id: str, provider_id: str | None) -> None:
    normalized = str(provider_id or "").strip().lower()
    if not normalized:
        return
    provider_catalog = get_ai_provider_catalog()
    known_provider_ids = {
        str(item.get("provider_id", "")).strip().lower()
        for item in provider_catalog.get("providers", [])
        if isinstance(item, dict)
    }
    if normalized not in known_provider_ids:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Selected runtime provider is unknown.",
                "details": {"reason_code": "STUDIO_PERSONA_PROVIDER_UNKNOWN", "provider_id": normalized},
            },
        )
    settings = studio_store.get_org_settings(tenant_id=tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    allowlist = org_settings.get("ai_provider_allowlist", [])
    if isinstance(allowlist, list):
        allowed = {str(item).strip().lower() for item in allowlist if str(item).strip()}
        if allowed and normalized not in allowed:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Selected runtime provider is not allowed for this organization.",
                    "details": {"reason_code": "STUDIO_PERSONA_PROVIDER_FORBIDDEN", "provider_id": normalized},
                },
            )


def _estimate_cost_per_message(*, token_count: int, model_profile: str) -> float:
    profile_cost_per_1k = {
        "fast": 0.0005,
        "balanced": 0.0015,
        "reasoning-optimized": 0.003,
    }
    unit = profile_cost_per_1k.get(model_profile, profile_cost_per_1k["reasoning-optimized"])
    return round((max(token_count, 1) / 1000.0) * unit, 6)


@router.post("/personas")
def create_persona(request: Request, payload: PersonaCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    _enforce_org_scope(auth, payload.org_id)
    _validate_runtime_provider(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        provider_id=payload.runtime_provider_id,
    )
    persona_data = _merge_persona_runtime(
        base_data=payload.data,
        runtime_provider_id=payload.runtime_provider_id,
        runtime_model_id=payload.runtime_model_id,
        fallback_policy=payload.fallback_policy,
    )
    persona = collaboration_store.create_persona(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        slug=payload.slug,
        role=payload.role,
        scope=payload.scope,
        enabled=payload.enabled,
        model_profile=payload.model_profile,
        system_prompt=payload.system_prompt,
        data=persona_data,
        created_by_user_id=auth.user_id,
    )
    version = collaboration_store.create_persona_version(
        tenant_id=auth.tenant_id,
        persona_id=persona["persona_id"],
        created_by_user_id=auth.user_id,
        bump="patch",
        change_summary="Initial persona version",
    )
    return ok_response(request, data={"persona": persona, "version": version})


@router.get("/personas")
def list_personas(
    request: Request,
    org_id: str | None = Query(default=None),
    enabled_only: bool = Query(default=False),
) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = org_id or auth.org_id
    if target_org_id:
        resolved_org = studio_store.resolve_organization_identifier(
            tenant_id=auth.tenant_id,
            identifier=target_org_id,
        )
        if resolved_org is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Organization not found.",
                    "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
                },
            )
        target_org_id = resolved_org["org_id"]
        _enforce_org_scope(auth, target_org_id)
        items = collaboration_store.list_personas(
            tenant_id=auth.tenant_id,
            org_id=target_org_id,
            enabled_only=enabled_only,
        )
    else:
        if not auth.is_global_admin:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Organization scope is required.",
                    "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
                },
            )
        items = collaboration_store.list_personas_any_org(
            tenant_id=auth.tenant_id,
            enabled_only=enabled_only,
        )
    settings = studio_store.get_org_settings(tenant_id=auth.tenant_id, org_id=target_org_id or "")
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    allowed_providers = org_settings.get("ai_provider_allowlist", [])
    allowed = (
        {str(item).strip().lower() for item in allowed_providers if str(item).strip()}
        if isinstance(allowed_providers, list)
        else set()
    )
    filtered: list[dict[str, Any]] = []
    for item in items:
        if not _can_access_persona(auth=auth, persona=item):
            continue
        provider_id, _ = _persona_runtime_model_settings(item)
        if provider_id and not is_provider_configured(provider_id):
            continue
        if provider_id and allowed and provider_id not in allowed:
            continue
        filtered.append(item)
    persona_chat_configuration = {
        "response_types": ["conversation", "markdown", "summary", "reporting"],
        "modes": ["single_best", "council", "summarized", "threaded", "silent_head"],
        "prompt_template_kinds": [
            "system_prompt",
            "planner_prompt",
            "tool_call_prompt",
            "focus_group_prompt",
            "tasking_prompt",
            "reflection_prompt",
        ],
    }
    enriched = [{**item, "voice": _persona_voice_profile(item), "chat_configuration": persona_chat_configuration} for item in filtered]
    return ok_response(request, data={"items": enriched})


@router.get("/personas/{persona_id}")
def get_persona(request: Request, persona_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth, persona["org_id"])
    if not _can_access_persona(auth=auth, persona=persona):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona access denied.",
                "details": {"reason_code": "STUDIO_PERSONA_ACCESS_FORBIDDEN"},
            },
        )
    provider_id, model_id = _persona_runtime_model_settings(persona)
    return ok_response(
        request,
        data={
            **persona,
            "voice": _persona_voice_profile(persona),
            "chat_configuration": {
                "response_types": ["conversation", "markdown", "summary", "reporting"],
                "modes": ["single_best", "council", "summarized", "threaded", "silent_head"],
                "runtime_provider_id": provider_id or "",
                "runtime_model_id": model_id or "",
                "prompt_template_kinds": [
                    "system_prompt",
                    "planner_prompt",
                    "tool_call_prompt",
                    "focus_group_prompt",
                    "tasking_prompt",
                    "reflection_prompt",
                ],
            },
        },
    )


@router.patch("/personas/{persona_id}")
def patch_persona(request: Request, persona_id: str, payload: PersonaPatchPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    existing = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth, existing["org_id"])
    provider_for_validation = payload.runtime_provider_id
    if provider_for_validation is None:
        existing_provider, _ = _persona_runtime_model_settings(existing)
        provider_for_validation = existing_provider
    _validate_runtime_provider(
        tenant_id=auth.tenant_id,
        org_id=existing["org_id"],
        provider_id=provider_for_validation,
    )

    if payload.version_bump not in {"patch", "major"}:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid version bump type.",
                "details": {"reason_code": "STUDIO_PERSONA_VERSION_BUMP_INVALID", "field": "version_bump"},
            },
        )

    incoming_data = payload.data if payload.data is not None else (existing.get("data", {}) if isinstance(existing.get("data"), dict) else {})
    merged_data = _merge_persona_runtime(
        base_data=incoming_data,
        runtime_provider_id=payload.runtime_provider_id,
        runtime_model_id=payload.runtime_model_id,
        fallback_policy=payload.fallback_policy,
    )

    updated = collaboration_store.update_persona(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
        name=payload.name,
        slug=payload.slug,
        role=payload.role,
        scope=payload.scope,
        enabled=payload.enabled,
        model_profile=payload.model_profile,
        system_prompt=payload.system_prompt,
        data=merged_data,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    version = collaboration_store.create_persona_version(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
        created_by_user_id=auth.user_id,
        bump=payload.version_bump,
        change_summary=payload.change_summary,
    )
    return ok_response(request, data={"persona": updated, "version": version})


@router.post("/personas/{persona_id}/approval")
def set_persona_approval(
    request: Request,
    persona_id: str,
    payload: PersonaApprovalPayload,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    existing = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth, existing["org_id"])

    approval_status = "approved" if payload.approved else "draft"
    updated = collaboration_store.set_persona_approval(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
        approval_status=approval_status,
        approved_by_user_id=auth.user_id if payload.approved else None,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    return ok_response(request, data=updated)


@router.get("/personas/{persona_id}/versions")
def list_persona_versions(request: Request, persona_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Persona not found.", "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, persona["org_id"])
    versions = collaboration_store.list_persona_versions(tenant_id=auth.tenant_id, persona_id=persona_id)
    return ok_response(request, data={"items": versions})


@router.get("/personas/{persona_id}/versions/{version_id}")
def get_persona_version(request: Request, persona_id: str, version_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Persona not found.", "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, persona["org_id"])
    version = collaboration_store.get_persona_version(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
        version_id=version_id,
    )
    if version is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona version not found.",
                "details": {"reason_code": "STUDIO_PERSONA_VERSION_NOT_FOUND"},
            },
        )
    return ok_response(request, data=version)


@router.post("/personas/{persona_id}/rollback/{version_id}")
def rollback_persona(request: Request, persona_id: str, version_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Persona not found.", "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, persona["org_id"])

    rolled_back = collaboration_store.rollback_persona_to_version(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
        version_id=version_id,
        changed_by_user_id=auth.user_id,
    )
    if rolled_back is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona version not found.",
                "details": {"reason_code": "STUDIO_PERSONA_VERSION_NOT_FOUND"},
            },
        )

    version = collaboration_store.create_persona_version(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
        created_by_user_id=auth.user_id,
        bump="patch",
        change_summary=f"Rollback from version {version_id}",
    )
    return ok_response(request, data={"persona": rolled_back, "version": version})


@router.get("/personas/{persona_id}/export-resume")
def export_persona_resume(
    request: Request,
    persona_id: str,
    provider_id: str | None = Query(default=None),
    model_id: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth, persona["org_id"])

    latest_version = collaboration_store.get_latest_persona_version(
        tenant_id=auth.tenant_id,
        persona_id=persona_id,
    )
    generated_prompt = (
        latest_version.get("generated_prompt")
        if isinstance(latest_version, dict)
        else compile_persona_system_prompt(persona)
    )
    token_count = (
        int(latest_version.get("token_count", 0))
        if isinstance(latest_version, dict)
        else max(len(str(generated_prompt).split()), 1)
    )
    version_string = (
        str(latest_version.get("version_string", "1.0.0"))
        if isinstance(latest_version, dict)
        else "1.0.0"
    )

    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    selected_options = data.get("selected_options", {}) if isinstance(data.get("selected_options"), dict) else {}
    guidelines = data.get("guidelines", {}) if isinstance(data.get("guidelines"), dict) else {}
    traits = selected_options.get("personality_traits", [])
    if not isinstance(traits, list):
        traits = []

    resume = {
        "persona_name": persona.get("name"),
        "role": persona.get("role"),
        "summary": data.get("description") or data.get("success_criteria") or "",
        "traits": [str(item) for item in traits],
        "communication_style": selected_options.get("communication_style", "balanced"),
        "initiative_level": selected_options.get("initiative_level", "moderate"),
        "expertise": data.get("skills", []),
        "tools": data.get("assigned_tools", []),
        "guidelines": {
            "do_list": guidelines.get("do_list", []),
            "dont_list": guidelines.get("dont_list", []),
            "guardrails": guidelines.get("guardrails", []),
        },
    }

    estimated_cost = _estimate_cost_per_message(
        token_count=token_count,
        model_profile=str(persona.get("model_profile", "reasoning-optimized")),
    )
    response_data = {
        "resume": resume,
        "metadata": {
            "prompt": generated_prompt,
            "token_count": token_count,
            "context_window": 128000,
            "estimated_cost_per_message": estimated_cost,
            "version": version_string,
            "approval_status": persona.get("approval_status", "draft"),
            "created_at": persona.get("created_at"),
        },
        "usage_forecast": {
            "avg_tokens_per_conversation": token_count * 3,
            "estimated_daily_cost": round(estimated_cost * 25, 6),
            "recommended_model": (
                "gpt-4o-mini"
                if str(persona.get("model_profile", "")) == "fast"
                else "claude-sonnet-4"
            ),
        },
        "provider_export": build_provider_resume_export(
            resume=resume,
            metadata={
                "version": version_string,
                "approval_status": persona.get("approval_status", "draft"),
            },
            provider_id=provider_id,
            model_id=model_id,
            policy_config=(
                (resume_adapter_policy_store.get_active_policy(
                    tenant_id=auth.tenant_id,
                    org_id=persona["org_id"],
                    name="default",
                ) or {}).get("config", {})
            ),
        ),
    }
    return ok_response(request, data=response_data)


@router.get("/users/{user_id}/persona-contexts")
def list_user_persona_contexts(request: Request, user_id: str) -> dict[str, Any]:
    auth = require_authentication(request)
    if auth.user_id != user_id and not auth.is_global_admin and not any(
        role in {"owner", "admin"} for role in auth.roles
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "User context access denied.",
                "details": {"reason_code": "STUDIO_USER_CONTEXT_FORBIDDEN"},
            },
        )
    items = collaboration_store.list_user_persona_contexts(tenant_id=auth.tenant_id, user_id=user_id)
    return ok_response(request, data={"items": items})


@router.get("/users/{user_id}/persona-contexts/{persona_id}")
def get_user_persona_context(request: Request, user_id: str, persona_id: str) -> dict[str, Any]:
    auth = require_authentication(request)
    if auth.user_id != user_id and not auth.is_global_admin and not any(
        role in {"owner", "admin"} for role in auth.roles
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "User context access denied.",
                "details": {"reason_code": "STUDIO_USER_CONTEXT_FORBIDDEN"},
            },
        )
    context = collaboration_store.get_user_persona_context(
        tenant_id=auth.tenant_id,
        user_id=user_id,
        persona_id=persona_id,
    )
    if context is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User persona context not found.",
                "details": {"reason_code": "STUDIO_USER_PERSONA_CONTEXT_NOT_FOUND"},
            },
        )
    return ok_response(request, data=context)


@router.put("/users/{user_id}/persona-contexts/{persona_id}")
def put_user_persona_context(
    request: Request,
    user_id: str,
    persona_id: str,
    payload: UserPersonaContextPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    if auth.user_id != user_id and not auth.is_global_admin and not any(
        role in {"owner", "admin"} for role in auth.roles
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "User context update denied.",
                "details": {"reason_code": "STUDIO_USER_CONTEXT_FORBIDDEN"},
            },
        )
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Persona not found.", "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"}},
        )
    context = collaboration_store.upsert_user_persona_context(
        tenant_id=auth.tenant_id,
        user_id=user_id,
        persona_id=persona_id,
        user_strengths=payload.user_strengths,
        user_weaknesses=payload.user_weaknesses,
        autonomy_level=payload.autonomy_level,
        communication_preference=payload.communication_preference,
        detail_level=payload.detail_level,
        check_in_frequency=payload.check_in_frequency,
        context=payload.context,
    )
    return ok_response(request, data=context)


@router.get("/channels/{channel_id}/council-config")
def get_council_config(request: Request, channel_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Channel not found.", "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, channel["org_id"])
    config = collaboration_store.get_room_council_config(tenant_id=auth.tenant_id, room_id=channel_id)
    personas = collaboration_store.list_room_personas(tenant_id=auth.tenant_id, room_id=channel_id)
    return ok_response(request, data={"config": config, "personas": personas})


@router.patch("/channels/{channel_id}/council-config")
def patch_council_config(
    request: Request,
    channel_id: str,
    payload: RoomCouncilConfigPayload,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Channel not found.", "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, channel["org_id"])
    if not _can_manage_channel(auth, channel):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Council config update forbidden.",
                "details": {"reason_code": "STUDIO_CHANNEL_POLICY_FORBIDDEN"},
            },
        )

    if payload.council_head_persona_id:
        head = collaboration_store.get_persona(
            tenant_id=auth.tenant_id,
            persona_id=payload.council_head_persona_id,
        )
        if head is None or head["org_id"] != channel["org_id"]:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Council head persona not found in organization.",
                    "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
                },
            )

    config = collaboration_store.upsert_room_council_config(
        tenant_id=auth.tenant_id,
        room_id=channel_id,
        council_head_persona_id=payload.council_head_persona_id,
        council_mode=payload.council_mode,
        delay_before_orchestration_ms=payload.delay_before_orchestration_ms,
        show_reasoning_metadata=payload.show_reasoning_metadata,
        allow_parallel_responses=payload.allow_parallel_responses,
    )
    return ok_response(request, data=config)


@router.put("/channels/{channel_id}/personas")
def put_channel_personas(
    request: Request,
    channel_id: str,
    payload: RoomPersonasPayload,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Channel not found.", "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, channel["org_id"])
    if not _can_manage_channel(auth, channel):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Channel persona assignment forbidden.",
                "details": {"reason_code": "STUDIO_CHANNEL_POLICY_FORBIDDEN"},
            },
        )

    for item in payload.personas:
        persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=item.persona_id)
        if persona is None or persona["org_id"] != channel["org_id"]:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Persona not found in organization.",
                    "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
                },
            )

    items = collaboration_store.set_room_personas(
        tenant_id=auth.tenant_id,
        room_id=channel_id,
        persona_items=[item.model_dump() for item in payload.personas],
    )
    return ok_response(request, data={"items": items})


@router.patch("/channels/{channel_id}/policy")
def patch_channel_policy(
    request: Request, channel_id: str, payload: ChannelPolicyPatchPayload
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Channel not found.",
                "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth, channel["org_id"])
    if not _can_manage_channel(auth, channel):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Channel policy update forbidden.",
                "details": {"reason_code": "STUDIO_CHANNEL_POLICY_FORBIDDEN"},
            },
        )

    if payload.default_persona_id:
        persona = collaboration_store.get_persona(
            tenant_id=auth.tenant_id,
            persona_id=payload.default_persona_id,
        )
        if persona is None or persona["org_id"] != channel["org_id"]:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Default persona not found in organization.",
                    "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
                },
            )

    updated = collaboration_store.update_channel_policy(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        response_policy=payload.response_policy,
        auto_respond=payload.auto_respond,
        responder_delay_seconds=payload.responder_delay_seconds,
        default_persona_id=payload.default_persona_id,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Channel not found.",
                "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"},
            },
        )
    return ok_response(request, data=updated)


@router.post("/channels/{channel_id}/chat")
def chat_in_channel(request: Request, channel_id: str, payload: ChannelChatPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    normalized_controls = normalize_chat_controls(payload.model_dump())
    if not bool(normalized_controls.get("accepted", False)):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Chat payload validation failed.",
                "details": {
                    "reason_code": "CHAT_PAYLOAD_VALIDATION_FAILED",
                    "rejections": normalized_controls.get("rejections", []),
                    "warnings": normalized_controls.get("warnings", []),
                    "validation_summary": normalized_controls.get("validation_summary", {}),
                },
            },
        )
    normalized = normalized_controls.get("normalized", {}) if isinstance(normalized_controls.get("normalized"), dict) else {}
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Channel not found.",
                "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth, channel["org_id"])
    if not collaboration_store.is_channel_participant(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        user_id=auth.user_id,
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Channel access denied.",
                "details": {"reason_code": "STUDIO_CHANNEL_ACCESS_DENIED"},
            },
        )

    user_message = collaboration_store.create_channel_message(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        sender_user_id=auth.user_id,
        content=str(normalized.get("content", payload.content)),
        metadata={
            "sender_kind": "user",
            "structured_content": {
                "version": "v1",
                "blocks": normalized.get("content_blocks", []),
            }
            if normalized.get("content_blocks")
            else {"version": "v1", "blocks": [{"type": "text", "text": str(normalized.get("content", payload.content))}]},
        },
    )

    explicit_calls = normalized.get("explicit_persona_calls", [])
    explicit_first = explicit_calls[0] if isinstance(explicit_calls, list) and explicit_calls else None
    requested_persona_id = explicit_first or normalized.get("persona_id")
    persona_id = requested_persona_id or channel.get("default_persona_id")
    persona = None
    if persona_id:
        persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
        if persona is None or persona["org_id"] != channel["org_id"]:
            if requested_persona_id:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Persona not found in organization.",
                        "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
                    },
                )
            persona = None
        if persona is not None and not _can_access_persona(auth=auth, persona=persona):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Persona access denied.",
                    "details": {"reason_code": "STUDIO_PERSONA_ACCESS_FORBIDDEN"},
                },
            )

    if persona is None:
        room_personas = collaboration_store.list_room_personas(tenant_id=auth.tenant_id, room_id=channel_id)
        for room_persona in room_personas:
            candidate_id = str(room_persona.get("persona_id", "")).strip()
            if not candidate_id:
                continue
            candidate = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=candidate_id)
            if candidate is None:
                continue
            if candidate.get("org_id") != channel["org_id"]:
                continue
            if not bool(candidate.get("enabled", True)):
                continue
            if not _can_access_persona(auth=auth, persona=candidate):
                continue
            persona = candidate
            persona_id = candidate_id
            break

    image_prompt = _infer_image_prompt(str(normalized.get("content", payload.content)))
    if image_prompt:
        provider_id = "google"
        model_id = "imagen-3.0-generate-002"
        if isinstance(persona, dict):
            runtime_provider, runtime_model = _persona_runtime_model_settings(persona)
            if runtime_provider in {"google", "openai"}:
                provider_id = runtime_provider
            if runtime_model:
                model_id = runtime_model

        if bool(normalized.get("auto_execute_tools", payload.auto_execute_tools)):
            output = generate_image_tool(
                prompt=image_prompt,
                provider_id=provider_id,
                model_id=model_id,
            )
            execution = tool_execution_store.create_execution(
                tenant_id=auth.tenant_id,
                org_id=channel["org_id"],
                tool_id="nano_banana",
                provider_id=str(output.get("provider_id", provider_id)),
                model_id=str(output.get("model_id", model_id)),
                input_payload={"prompt": image_prompt},
                output_payload=output,
                created_by_user_id=auth.user_id,
                status=str(output.get("status", "completed")),
            )
        else:
            output = {
                "provider_id": provider_id,
                "model_id": model_id,
                "mime_type": "image/png",
                "status": "recommended",
                "note": "Tool call was recommended but not executed.",
            }
            execution = {"execution_id": "", "provider_id": provider_id, "model_id": model_id}
        attachments = [
            {
                "type": "image",
                "mime_type": str(output.get("mime_type", "image/png")),
                "asset_url": str(output.get("asset_url", "")),
                "image_base64": str(output.get("image_base64", "")),
                "status": str(output.get("status", "")),
            }
        ]
        assistant_message = collaboration_store.create_channel_message(
            tenant_id=auth.tenant_id,
            channel_id=channel_id,
            sender_user_id=auth.user_id,
            content=(
                "Generated image from prompt."
                if bool(normalized.get("auto_execute_tools", payload.auto_execute_tools))
                else "Image recommendation prepared."
            ),
            metadata={
                "sender_kind": "assistant",
                "mode": str(normalized.get("mode", payload.mode)),
                "response_type": str(normalized.get("response_type", payload.response_type)),
                "tool_call": {
                    "tool_id": "nano_banana",
                    "execution_id": execution.get("execution_id"),
                    "provider": execution.get("provider_id"),
                    "model": execution.get("model_id"),
                },
                "attachments": attachments,
                "structured_content": _build_structured_content(
                    text=("Generated image from prompt." if bool(normalized.get("auto_execute_tools", payload.auto_execute_tools)) else "Image recommendation prepared."),
                    response_type=str(normalized.get("response_type", payload.response_type)),
                    attachments=attachments,
                ),
                "tool_recommendations": [
                    {
                        "tool_id": "nano_banana",
                        "capability": "image_generation",
                        "recommended": True,
                        "reason": "image_intent_detected",
                    }
                ],
            },
        )
        return ok_response(
            request,
            data={
                "user_message": user_message,
                "assistant_message": assistant_message,
                "chat_options": _build_chat_options(
                    tenant_id=auth.tenant_id,
                    org_id=channel["org_id"],
                    channel_id=channel_id,
                    selected_persona_id=persona.get("persona_id") if isinstance(persona, dict) else None,
                ),
                "requested_controls": {
                    "response_type": str(normalized.get("response_type", payload.response_type)),
                    "persona_overrides": normalized.get("participant_controls", {}),
                    "auto_execute_tools": bool(normalized.get("auto_execute_tools", payload.auto_execute_tools)),
                },
                "validation": {
                    "warnings": normalized_controls.get("warnings", []),
                    "rejections": normalized_controls.get("rejections", []),
                    "summary": normalized_controls.get("validation_summary", {}),
                },
            },
        )

    messages = collaboration_store.build_conversation_messages(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        limit=40,
    )
    settings = studio_store.get_org_settings(tenant_id=auth.tenant_id, org_id=channel["org_id"])
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    compaction_level = str(org_settings.get("context_compaction_level", "medium"))
    persona_data = persona.get("data", {}) if isinstance(persona and persona.get("data"), dict) else {}
    persona_runtime = persona_data.get("runtime", {}) if isinstance(persona_data.get("runtime"), dict) else {}
    compaction_disabled = bool(persona_runtime.get("disable_compaction", False))
    context_result = context_window_service.prepare_messages(
        messages=messages,
        level=compaction_level,
        disabled=compaction_disabled,
    )

    system_prompt = ""
    model_profile = "reasoning-optimized"
    provider_override = None
    model_override = None
    if persona is not None:
        _enforce_persona_policy(tenant_id=auth.tenant_id, org_id=channel["org_id"], persona=persona)
        base_system_prompt = compile_persona_system_prompt_resolved(
            tenant_id=auth.tenant_id,
            persona=persona,
            org_id=channel["org_id"],
            team_id=str(channel.get("team_id", "") or ""),
        )
        runtime_provider_id, _ = _persona_runtime_model_settings(persona)
        tool_call_extension = resolve_rendered_prompt_template(
            tenant_id=auth.tenant_id,
            provider_id=runtime_provider_id or "openai",
            template_kind="tool_call_prompt",
            scopes={
                "team": str(channel.get("team_id", "") or ""),
                "division": "",
                "org": channel["org_id"],
                "tenant": auth.tenant_id,
            },
            context={
                "persona": {
                    "name": persona.get("name", ""),
                    "role": persona.get("role", ""),
                    "scope": persona.get("scope", "organization"),
                },
                "request": {
                    "message": str(normalized.get("content", payload.content)),
                    "mode": str(normalized.get("mode", payload.mode)),
                },
            },
        )
        system_prompt = _append_prompt(base_system_prompt, tool_call_extension)
        model_profile = persona.get("model_profile", "reasoning-optimized")
        provider_override, model_override = _persona_runtime_model_settings(persona)

    system_prompt = _append_prompt(
        system_prompt,
        _response_type_instruction(str(normalized.get("response_type", payload.response_type))),
    )

    try:
        result = model_gateway.generate_text_sync(
            ModelRequest(
                system_prompt=system_prompt,
                conversation_messages=context_result.messages,
                model_profile=model_profile,
                provider_id=provider_override,
                model_id=model_override,
                tenant_id=auth.tenant_id,
                org_id=channel["org_id"],
            )
        )
    except Exception as error:
        fallback_policy = _persona_fallback_policy(persona)
        fallback_provider_id = str(fallback_policy.get("provider_id", "")).strip().lower()
        fallback_model_id = str(fallback_policy.get("model_id", "")).strip()
        approval_required = bool(fallback_policy.get("approval_required", True))
        enabled = bool(fallback_policy.get("enabled", False))
        if enabled and approval_required and fallback_provider_id and fallback_model_id:
            consumed_approval = fallback_store.consume_approved_request(
                tenant_id=auth.tenant_id,
                org_id=channel["org_id"],
                room_id=channel_id,
                persona_id=persona.get("persona_id") if persona else "",
                source_provider_id=provider_override or "",
                source_model_id=model_override or "",
                fallback_provider_id=fallback_provider_id,
                fallback_model_id=fallback_model_id,
            )
            if consumed_approval is not None:
                result = model_gateway.generate_text_sync(
                    ModelRequest(
                        system_prompt=system_prompt,
                        conversation_messages=context_result.messages,
                        model_profile=model_profile,
                        provider_id=fallback_provider_id,
                        model_id=fallback_model_id,
                        tenant_id=auth.tenant_id,
                        org_id=channel["org_id"],
                    )
                )
                audit_store.record_event(
                    tenant_id=auth.tenant_id,
                    actor_type="user",
                    actor_id=auth.user_id,
                    action="fallback.executed",
                    resource_type="fallback_approval_request",
                    resource_id=consumed_approval["request_id"],
                    room_id=channel_id,
                    decision="allowed",
                    reason_code="FALLBACK_APPROVAL_CONSUMED",
                    metadata={
                        "source_provider_id": provider_override or "",
                        "source_model_id": model_override or "",
                        "fallback_provider_id": fallback_provider_id,
                        "fallback_model_id": fallback_model_id,
                    },
                )
                
                assistant_message = collaboration_store.create_channel_message(
                    tenant_id=auth.tenant_id,
                    channel_id=channel_id,
                    sender_user_id=auth.user_id,
                    content=result.content,
                    metadata={
                        "sender_kind": "assistant",
                        "provider": result.provider,
                        "model": result.model,
                        "usage": result.usage,
                        "persona_id": persona.get("persona_id") if persona else None,
                        "mode": str(normalized.get("mode", payload.mode)),
                        "response_type": str(normalized.get("response_type", payload.response_type)),
                        "fallback_approval_request_id": consumed_approval["request_id"],
                        "context_window": {
                            "raw_token_estimate": context_result.raw_token_estimate,
                            "compacted_token_estimate": context_result.compacted_token_estimate,
                            "tokens_saved_estimate": context_result.tokens_saved_estimate,
                            "compaction_applied": context_result.compaction_applied,
                            "compaction_level": compaction_level,
                            "compaction_disabled": compaction_disabled,
                        },
                        "structured_content": _build_structured_content(
                            text=result.content,
                            response_type=str(normalized.get("response_type", payload.response_type)),
                        ),
                    },
                )
                return ok_response(
                    request,
                    data={
                        "user_message": user_message,
                        "assistant_message": assistant_message,
                        "chat_options": _build_chat_options(
                            tenant_id=auth.tenant_id,
                            org_id=channel["org_id"],
                            channel_id=channel_id,
                            selected_persona_id=persona.get("persona_id") if isinstance(persona, dict) else None,
                        ),
                        "requested_controls": {
                            "response_type": str(normalized.get("response_type", payload.response_type)),
                            "persona_overrides": normalized.get("participant_controls", {}),
                            "auto_execute_tools": bool(normalized.get("auto_execute_tools", payload.auto_execute_tools)),
                        },
                        "validation": {
                            "warnings": normalized_controls.get("warnings", []),
                            "rejections": normalized_controls.get("rejections", []),
                            "summary": normalized_controls.get("validation_summary", {}),
                        },
                    },
                )

            approval_request = fallback_store.create_request(
                tenant_id=auth.tenant_id,
                org_id=channel["org_id"],
                room_id=channel_id,
                orchestration_run_id="",
                persona_id=persona.get("persona_id") if persona else "",
                source_provider_id=provider_override or "",
                source_model_id=model_override or "",
                fallback_provider_id=fallback_provider_id,
                fallback_model_id=fallback_model_id,
                trigger_reason="chat_generation_error",
                created_by_user_id=auth.user_id,
                metadata={
                    "mode": str(normalized.get("mode", payload.mode)),
                    "error": str(error),
                },
            )
            audit_store.record_event(
                tenant_id=auth.tenant_id,
                actor_type="user",
                actor_id=auth.user_id,
                action="fallback.approval.required",
                resource_type="fallback_approval_request",
                resource_id=approval_request["request_id"],
                room_id=channel_id,
                decision="deferred",
                reason_code="FALLBACK_APPROVAL_REQUIRED",
                metadata={
                    "persona_id": persona.get("persona_id") if persona else "",
                    "source_provider_id": provider_override or "",
                    "source_model_id": model_override or "",
                    "fallback_provider_id": fallback_provider_id,
                    "fallback_model_id": fallback_model_id,
                    "trigger_reason": "chat_generation_error",
                },
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Fallback execution requires approval.",
                    "details": {
                        "reason_code": "STUDIO_FALLBACK_APPROVAL_REQUIRED",
                        "request_id": approval_request["request_id"],
                    },
                },
            ) from error
        raise

    assistant_message = collaboration_store.create_channel_message(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        sender_user_id=auth.user_id,
        content=result.content,
        metadata={
            "sender_kind": "assistant",
            "provider": result.provider,
            "model": result.model,
            "usage": result.usage,
            "persona_id": persona.get("persona_id") if persona else None,
            "mode": str(normalized.get("mode", payload.mode)),
            "response_type": str(normalized.get("response_type", payload.response_type)),
            "context_window": {
                "raw_token_estimate": context_result.raw_token_estimate,
                "compacted_token_estimate": context_result.compacted_token_estimate,
                "tokens_saved_estimate": context_result.tokens_saved_estimate,
                "compaction_applied": context_result.compaction_applied,
                "compaction_level": compaction_level,
                "compaction_disabled": compaction_disabled,
            },
            "structured_content": _build_structured_content(
                text=result.content,
                response_type=str(normalized.get("response_type", payload.response_type)),
            ),
        },
    )

    return ok_response(
        request,
        data={
            "user_message": user_message,
            "assistant_message": assistant_message,
            "chat_options": _build_chat_options(
                tenant_id=auth.tenant_id,
                org_id=channel["org_id"],
                channel_id=channel_id,
                selected_persona_id=persona.get("persona_id") if isinstance(persona, dict) else None,
            ),
            "requested_controls": {
                "response_type": str(normalized.get("response_type", payload.response_type)),
                "persona_overrides": normalized.get("participant_controls", {}),
                "auto_execute_tools": bool(normalized.get("auto_execute_tools", payload.auto_execute_tools)),
            },
            "validation": {
                "warnings": normalized_controls.get("warnings", []),
                "rejections": normalized_controls.get("rejections", []),
                "summary": normalized_controls.get("validation_summary", {}),
            },
        },
    )
