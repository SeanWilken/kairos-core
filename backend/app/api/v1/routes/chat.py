from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.audit_store import audit_store
from app.core.auth_context import AuthContext, require_authentication, require_roles
from app.core.collaboration_store import collaboration_store
from app.core.context_window_service import context_window_service
from app.core.fallback_store import fallback_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.persona_prompt import compile_persona_system_prompt, compile_persona_system_prompt_resolved
from app.core.resume_export_adapter import build_provider_resume_export
from app.core.resume_adapter_policy_store import resume_adapter_policy_store
from app.core.response import ok_response
from app.core.studio_store import studio_store
from app.core.tool_provider_registry import is_provider_configured

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
    content: str = Field(min_length=1)
    persona_id: str | None = None
    mode: str = Field(default="single_best")


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


def _validate_runtime_provider(*, tenant_id: str, org_id: str, provider_id: str | None) -> None:
    normalized = str(provider_id or "").strip().lower()
    if not normalized:
        return
    if not is_provider_configured(normalized):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Selected runtime provider is not configured.",
                "details": {"reason_code": "STUDIO_PERSONA_PROVIDER_UNAVAILABLE", "provider_id": normalized},
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
    org_id: str = Query(min_length=1),
    enabled_only: bool = Query(default=False),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, org_id)
    items = collaboration_store.list_personas(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        enabled_only=enabled_only,
    )
    settings = studio_store.get_org_settings(tenant_id=auth.tenant_id, org_id=org_id)
    org_settings = settings.get("settings", {}) if isinstance(settings, dict) else {}
    allowed_providers = org_settings.get("ai_provider_allowlist", [])
    allowed = (
        {str(item).strip().lower() for item in allowed_providers if str(item).strip()}
        if isinstance(allowed_providers, list)
        else set()
    )
    filtered: list[dict[str, Any]] = []
    for item in items:
        provider_id, _ = _persona_runtime_model_settings(item)
        if provider_id and not is_provider_configured(provider_id):
            continue
        if provider_id and allowed and provider_id not in allowed:
            continue
        filtered.append(item)
    return ok_response(request, data={"items": filtered})


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
    return ok_response(request, data=persona)


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
        content=payload.content,
        metadata={"sender_kind": "user"},
    )

    persona_id = payload.persona_id or channel.get("default_persona_id")
    persona = None
    if persona_id:
        persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
        if persona is None or persona["org_id"] != channel["org_id"]:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Persona not found in organization.",
                    "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
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
        system_prompt = compile_persona_system_prompt_resolved(
            tenant_id=auth.tenant_id,
            persona=persona,
            org_id=channel["org_id"],
            team_id=str(channel.get("team_id", "") or ""),
        )
        model_profile = persona.get("model_profile", "reasoning-optimized")
        provider_override, model_override = _persona_runtime_model_settings(persona)

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
                        "mode": payload.mode,
                        "fallback_approval_request_id": consumed_approval["request_id"],
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
                return ok_response(
                    request,
                    data={
                        "user_message": user_message,
                        "assistant_message": assistant_message,
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
                    "mode": payload.mode,
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
            "mode": payload.mode,
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

    return ok_response(
        request,
        data={
            "user_message": user_message,
            "assistant_message": assistant_message,
        },
    )
