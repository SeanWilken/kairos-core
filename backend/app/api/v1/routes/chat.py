from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.ai_provider import generate_chat_completion
from app.core.auth_context import AuthContext, require_authentication, require_roles
from app.core.collaboration_store import collaboration_store
from app.core.persona_prompt import compile_persona_system_prompt
from app.core.response import ok_response

router = APIRouter(prefix="/studio", tags=["studio-chat"])


class PersonaCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    role: str = Field(min_length=1)
    scope: str = Field(default="organization")
    enabled: bool = True
    model_profile: str = Field(default="reasoning-optimized")
    system_prompt: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class PersonaPatchPayload(BaseModel):
    name: str | None = None
    slug: str | None = None
    role: str | None = None
    scope: str | None = None
    enabled: bool | None = None
    model_profile: str | None = None
    system_prompt: str | None = None
    data: dict[str, Any] | None = None


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


@router.post("/personas")
def create_persona(request: Request, payload: PersonaCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    _enforce_org_scope(auth, payload.org_id)
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
        data=payload.data,
        created_by_user_id=auth.user_id,
    )
    return ok_response(request, data=persona)


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
    return ok_response(request, data={"items": items})


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
        data=payload.data,
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

    system_prompt = ""
    model_profile = "reasoning-optimized"
    if persona is not None:
        system_prompt = compile_persona_system_prompt(persona)
        model_profile = persona.get("model_profile", "reasoning-optimized")

    result = generate_chat_completion(
        system_prompt=system_prompt,
        conversation_messages=messages,
        model_profile=model_profile,
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
        },
    )

    return ok_response(
        request,
        data={
            "user_message": user_message,
            "assistant_message": assistant_message,
        },
    )
