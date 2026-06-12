from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.auth_context import require_authentication
from app.core.auth_store import auth_store
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.db_models import TenantModel
from app.core.response import ok_response
from app.core.security import (
    decode_jwt,
    hash_secret,
    issue_jwt,
    make_password_hash,
    verify_password,
)
from app.core.studio_store import studio_store
from app.core.tenant_policy import require_existing_tenant, validate_tenant_scope

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterPayload(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = ""
    tenant_id: str | None = None
    org_id: str | None = None
    is_global_admin: bool = False
    role: str = "member"


class LoginPayload(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    tenant_id: str | None = None
    org_id: str | None = None


class RefreshPayload(BaseModel):
    refresh_token: str = Field(min_length=20)


class ContextSwitchPayload(BaseModel):
    org_id: str = Field(min_length=1)


def _resolve_tenant(request: Request, payload_tenant: str | None) -> str:
    if payload_tenant:
        tenant_id = payload_tenant
    else:
        tenant_id = request.headers.get("X-Tenant-ID") or ""

    if not tenant_id:
        settings = get_settings()
        if settings.single_tenant_mode and settings.install_tenant_id:
            tenant_id = settings.install_tenant_id
        elif settings.single_tenant_mode:
            with SessionLocal() as db:
                rows = db.scalars(select(TenantModel).order_by(TenantModel.created_at.asc()).limit(2)).all()
                if len(rows) == 1:
                    tenant_id = rows[0].tenant_id

    if not tenant_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Tenant context is required.",
                "details": {"reason_code": "TENANT_CONTEXT_MISSING"},
            },
        )

    validate_tenant_scope(tenant_id)
    require_existing_tenant(tenant_id)
    return tenant_id


def _token_pair_for_user(
    *,
    user: dict[str, Any],
    org_id: str | None,
    roles: list[str],
) -> dict[str, Any]:
    settings = get_settings()
    access_ttl = settings.jwt_access_token_ttl_minutes * 60
    refresh_ttl = settings.jwt_refresh_token_ttl_days * 24 * 60 * 60

    base_claims = {
        "sub": user["user_id"],
        "tenant_id": user["tenant_id"],
        "org_id": org_id or "",
        "is_global_admin": bool(user.get("is_global_admin", False)),
        "roles": roles,
    }

    access_token = issue_jwt(base_claims, token_type="access", ttl_seconds=access_ttl)
    refresh_token = issue_jwt(base_claims, token_type="refresh", ttl_seconds=refresh_ttl)
    refresh_claims = decode_jwt(refresh_token)
    auth_store.create_refresh_token(
        token_id=refresh_claims["jti"],
        user_id=user["user_id"],
        tenant_id=user["tenant_id"],
        org_id=org_id,
        token_hash=hash_secret(refresh_token),
        expires_at=datetime.fromtimestamp(refresh_claims["exp"], tz=timezone.utc),
    )

    return {
        "token_type": "bearer",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": access_ttl,
    }


@router.post("/register")
def register(request: Request, payload: RegisterPayload) -> dict[str, Any]:
    tenant_id = _resolve_tenant(request, payload.tenant_id)
    org_id = payload.org_id

    if not payload.is_global_admin and not org_id:
        org_header = request.headers.get("X-Org-ID")
        org_id = org_header or None
    if org_id:
        org = studio_store.get_organization(tenant_id=tenant_id, org_id=org_id)
        if org is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Organization not found.",
                    "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
                },
            )

    existing = studio_store.get_user_by_email(tenant_id=tenant_id, email=payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Email already exists.",
                "details": {"reason_code": "STUDIO_USER_EMAIL_EXISTS", "field": "email"},
            },
        )

    user = studio_store.create_user(
        tenant_id=tenant_id,
        org_id=org_id,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        is_global_admin=payload.is_global_admin,
        role=payload.role,
    )
    auth_store.upsert_password_hash(
        user_id=user["user_id"],
        password_hash=make_password_hash(payload.password),
    )
    roles = [payload.role] if org_id else []
    if payload.is_global_admin:
        roles.append("global_admin")
    tokens = _token_pair_for_user(user=user, org_id=org_id, roles=roles)
    return ok_response(request, data={"user": user, **tokens})


@router.post("/login")
def login(request: Request, payload: LoginPayload) -> dict[str, Any]:
    tenant_id = _resolve_tenant(request, payload.tenant_id)
    user = studio_store.get_user_by_email(tenant_id=tenant_id, email=payload.email)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid email or password.",
                "details": {"reason_code": "AUTH_INVALID_CREDENTIALS"},
            },
        )

    password_hash = auth_store.get_password_hash(user_id=user["user_id"])
    if not password_hash or not verify_password(payload.password, password_hash):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid email or password.",
                "details": {"reason_code": "AUTH_INVALID_CREDENTIALS"},
            },
        )

    memberships = studio_store.list_user_memberships(
        tenant_id=tenant_id,
        user_id=user["user_id"],
    )
    selected_org_id = payload.org_id
    selected_role = ""
    if selected_org_id:
        membership = next((item for item in memberships if item["org_id"] == selected_org_id), None)
        if membership is None and not user.get("is_global_admin", False):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "User is not a member of this organization.",
                    "details": {"reason_code": "AUTH_ORG_MEMBERSHIP_REQUIRED"},
                },
            )
        if membership:
            selected_role = membership["role"]
    elif memberships:
        selected_org_id = memberships[0]["org_id"]
        selected_role = memberships[0]["role"]

    roles = [selected_role] if selected_role else []
    if user.get("is_global_admin", False):
        roles.append("global_admin")
    tokens = _token_pair_for_user(user=user, org_id=selected_org_id, roles=roles)
    return ok_response(request, data={"user": user, **tokens})


@router.post("/refresh")
def refresh(request: Request, payload: RefreshPayload) -> dict[str, Any]:
    try:
        claims = decode_jwt(payload.refresh_token)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail={
                "message": str(error),
                "details": {"reason_code": "AUTH_REFRESH_INVALID"},
            },
        ) from error

    if claims.get("token_type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Refresh token is required.",
                "details": {"reason_code": "AUTH_REFRESH_INVALID"},
            },
        )

    token_id = claims.get("jti")
    if not isinstance(token_id, str):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Refresh token is invalid.",
                "details": {"reason_code": "AUTH_REFRESH_INVALID"},
            },
        )

    stored = auth_store.get_refresh_token(token_id=token_id)
    if stored is None or stored.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Refresh token is invalid.",
                "details": {"reason_code": "AUTH_REFRESH_INVALID"},
            },
        )

    stored_expires_at = stored.expires_at
    if stored_expires_at.tzinfo is None:
        stored_expires_at = stored_expires_at.replace(tzinfo=timezone.utc)

    if stored_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Refresh token expired.",
                "details": {"reason_code": "AUTH_REFRESH_EXPIRED"},
            },
        )

    if stored.token_hash != hash_secret(payload.refresh_token):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Refresh token is invalid.",
                "details": {"reason_code": "AUTH_REFRESH_INVALID"},
            },
        )

    user = studio_store.get_user(tenant_id=stored.tenant_id, user_id=stored.user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "User not found for refresh token.",
                "details": {"reason_code": "AUTH_REFRESH_INVALID"},
            },
        )

    memberships = studio_store.list_user_memberships(
        tenant_id=stored.tenant_id,
        user_id=stored.user_id,
    )
    selected_role = ""
    if stored.org_id:
        membership = next((item for item in memberships if item["org_id"] == stored.org_id), None)
        if membership:
            selected_role = membership["role"]

    roles = [selected_role] if selected_role else []
    if user.get("is_global_admin", False):
        roles.append("global_admin")

    auth_store.revoke_refresh_token(token_id=token_id)
    tokens = _token_pair_for_user(
        user=user,
        org_id=stored.org_id or None,
        roles=roles,
    )
    return ok_response(request, data={"user": user, **tokens})


@router.post("/logout")
def logout(request: Request, payload: RefreshPayload) -> dict[str, Any]:
    try:
        claims = decode_jwt(payload.refresh_token)
    except ValueError:
        return ok_response(request, data={"revoked": False})

    token_id = claims.get("jti")
    if isinstance(token_id, str):
        auth_store.revoke_refresh_token(token_id=token_id)
    return ok_response(request, data={"revoked": True})


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    context = require_authentication(request)
    user = studio_store.get_user(tenant_id=context.tenant_id, user_id=context.user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User not found.",
                "details": {"reason_code": "STUDIO_USER_NOT_FOUND"},
            },
        )

    memberships = studio_store.list_user_memberships(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )
    organizations = studio_store.list_organizations(tenant_id=context.tenant_id)
    org_map = {item["org_id"]: item for item in organizations}
    org_options = []
    seen_org_ids: set[str] = set()
    for membership in memberships:
        org = org_map.get(membership["org_id"])
        if org is None:
            continue
        seen_org_ids.add(org["org_id"])
        org_options.append(
            {
                "org_id": org["org_id"],
                "name": org["name"],
                "slug": org["slug"],
                "role": membership.get("role", "member"),
            }
        )

    if context.is_global_admin:
        for org in organizations:
            org_id = str(org.get("org_id", "")).strip()
            if not org_id or org_id in seen_org_ids:
                continue
            org_options.append(
                {
                    "org_id": org_id,
                    "name": org.get("name", ""),
                    "slug": org.get("slug", ""),
                    "role": "global_admin",
                }
            )
    return ok_response(
        request,
        data={
            "user": user,
            "auth": {
                "tenant_id": context.tenant_id,
                "org_id": context.org_id,
                "roles": context.roles,
                "is_global_admin": context.is_global_admin,
            },
            "memberships": memberships,
            "org_options": org_options,
        },
    )


@router.post("/context/switch")
def switch_context(request: Request, payload: ContextSwitchPayload) -> dict[str, Any]:
    context = require_authentication(request)
    user = studio_store.get_user(tenant_id=context.tenant_id, user_id=context.user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User not found.",
                "details": {"reason_code": "STUDIO_USER_NOT_FOUND"},
            },
        )

    resolved_org = studio_store.resolve_organization_identifier(
        tenant_id=context.tenant_id,
        identifier=payload.org_id,
    )
    if resolved_org is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        )

    memberships = studio_store.list_user_memberships(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
    )
    membership = next((item for item in memberships if item["org_id"] == resolved_org["org_id"]), None)
    if membership is None and not context.is_global_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "User is not a member of this organization.",
                "details": {"reason_code": "AUTH_ORG_MEMBERSHIP_REQUIRED"},
            },
        )

    roles = [membership["role"]] if membership else []
    if bool(user.get("is_global_admin", False)):
        roles.append("global_admin")
    tokens = _token_pair_for_user(
        user=user,
        org_id=resolved_org["org_id"],
        roles=roles,
    )
    return ok_response(
        request,
        data={
            "org": {
                "org_id": resolved_org["org_id"],
                "name": resolved_org["name"],
                "slug": resolved_org["slug"],
            },
            **tokens,
        },
    )
