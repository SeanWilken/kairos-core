from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication, require_roles
from app.core.response import ok_response
from app.core.studio_store import studio_store

router = APIRouter(prefix="/studio", tags=["studio"])


class StudioOrganizationCreatePayload(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    mode: str = Field(default="team")
    owner_user_id: str | None = None


class StudioUserCreatePayload(BaseModel):
    email: str = Field(min_length=3)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    phone: str = ""
    status: str = "active"
    is_global_admin: bool = False
    org_id: str | None = None
    role: str = "member"


class StudioMembershipCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    role: str = "member"
    status: str = "active"


class StudioMembershipPatchPayload(BaseModel):
    role: str | None = None
    status: str | None = None


class StudioInviteCreatePayload(BaseModel):
    org_id: str | None = None
    email: str = Field(min_length=3)
    role: str = "member"
    expires_in_days: int = Field(default=7, ge=1, le=30)


class StudioInviteAcceptPayload(BaseModel):
    org_id: str | None = None


class StudioOrgSettingsPatchPayload(BaseModel):
    org_id: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class StudioOnboardingCompletePayload(BaseModel):
    org_id: str | None = None
    checklist: dict[str, bool] | None = None


def _enforce_org_scope(
    auth_org_id: str | None, target_org_id: str | None, *, is_global_admin: bool
) -> None:
    if is_global_admin:
        return
    if not auth_org_id or not target_org_id or auth_org_id != target_org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Operation is outside current organization scope.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )


def _resolve_target_org_id(request: Request, auth_org_id: str | None, payload_org_id: str | None) -> str:
    target_org_id = payload_org_id or auth_org_id or request.query_params.get("org_id")
    if not target_org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization context is required.",
                "details": {"reason_code": "STUDIO_ORG_REQUIRED", "field": "org_id"},
            },
        )
    return target_org_id


@router.post("/organizations")
def create_organization(
    request: Request, payload: StudioOrganizationCreatePayload
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    organization = studio_store.create_organization(
        tenant_id=auth.tenant_id,
        name=payload.name,
        slug=payload.slug,
        mode=payload.mode,
        owner_user_id=payload.owner_user_id,
    )
    return ok_response(request, data=organization)


@router.get("/organizations")
def list_organizations(request: Request) -> dict[str, Any]:
    auth = require_authentication(request)
    organizations = studio_store.list_organizations(tenant_id=auth.tenant_id)
    return ok_response(request, data={"items": organizations})


@router.get("/organizations/{org_id}")
def get_organization(request: Request, org_id: str) -> dict[str, Any]:
    auth = require_authentication(request)
    _enforce_org_scope(auth.org_id, org_id, is_global_admin=auth.is_global_admin)
    organization = studio_store.get_organization(tenant_id=auth.tenant_id, org_id=org_id)
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        )
    return ok_response(request, data=organization)


@router.post("/users")
def create_user(request: Request, payload: StudioUserCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    org_id = payload.org_id

    if payload.is_global_admin:
        org_id = payload.org_id
    elif org_id is None:
        org_id = auth.org_id

    if not payload.is_global_admin and not org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization context is required for non-global users.",
                "details": {"reason_code": "STUDIO_ORG_REQUIRED_FOR_USER", "field": "org_id"},
            },
        )

    _enforce_org_scope(auth.org_id, org_id, is_global_admin=auth.is_global_admin)

    if org_id is not None:
        organization = studio_store.get_organization(tenant_id=auth.tenant_id, org_id=org_id)
        if organization is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Organization not found.",
                    "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
                },
            )

    existing = studio_store.get_user_by_email(tenant_id=auth.tenant_id, email=payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Email already exists.",
                "details": {"reason_code": "STUDIO_USER_EMAIL_EXISTS", "field": "email"},
            },
        )

    user = studio_store.create_user(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        status=payload.status,
        is_global_admin=payload.is_global_admin,
        role=payload.role,
    )
    return ok_response(request, data=user)


@router.get("/users")
def list_users(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = org_id or auth.org_id
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    users = studio_store.list_users(tenant_id=auth.tenant_id, org_id=target_org_id)
    return ok_response(request, data={"items": users})


@router.get("/users/{user_id}")
def get_user(request: Request, user_id: str) -> dict[str, Any]:
    auth = require_authentication(request)
    user = studio_store.get_user(tenant_id=auth.tenant_id, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User not found.",
                "details": {"reason_code": "STUDIO_USER_NOT_FOUND"},
            },
        )
    if not auth.is_global_admin and auth.org_id:
        memberships = studio_store.list_user_memberships(tenant_id=auth.tenant_id, user_id=user_id)
        if not any(item["org_id"] == auth.org_id for item in memberships):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "User is outside current organization scope.",
                    "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
                },
            )
    return ok_response(request, data=user)


@router.post("/memberships")
def create_membership(request: Request, payload: StudioMembershipCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    _enforce_org_scope(auth.org_id, payload.org_id, is_global_admin=auth.is_global_admin)

    organization = studio_store.get_organization(tenant_id=auth.tenant_id, org_id=payload.org_id)
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        )

    user = studio_store.get_user(tenant_id=auth.tenant_id, user_id=payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User not found.",
                "details": {"reason_code": "STUDIO_USER_NOT_FOUND"},
            },
        )

    existing = studio_store.get_membership_by_org_user(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        user_id=payload.user_id,
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Membership already exists.",
                "details": {"reason_code": "STUDIO_MEMBERSHIP_EXISTS"},
            },
        )

    membership = studio_store.create_membership(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        user_id=payload.user_id,
        role=payload.role,
        status=payload.status,
    )
    return ok_response(request, data=membership)


@router.patch("/memberships/{membership_id}")
def patch_membership(
    request: Request, membership_id: str, payload: StudioMembershipPatchPayload
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})

    if payload.role is None and payload.status is None:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "At least one field must be provided.",
                "details": {"reason_code": "STUDIO_MEMBERSHIP_PATCH_EMPTY"},
            },
        )

    existing = studio_store.get_membership(tenant_id=auth.tenant_id, membership_id=membership_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Membership not found.",
                "details": {"reason_code": "STUDIO_MEMBERSHIP_NOT_FOUND"},
            },
        )
    _enforce_org_scope(auth.org_id, existing["org_id"], is_global_admin=auth.is_global_admin)

    membership = studio_store.update_membership(
        tenant_id=auth.tenant_id,
        membership_id=membership_id,
        role=payload.role,
        status=payload.status,
    )
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Membership not found.",
                "details": {"reason_code": "STUDIO_MEMBERSHIP_NOT_FOUND"},
            },
        )

    return ok_response(request, data=membership)


@router.get("/governance/baseline")
def get_governance_baseline(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = _resolve_target_org_id(request, auth.org_id, org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)

    organization = studio_store.get_organization(tenant_id=auth.tenant_id, org_id=target_org_id)
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        )

    settings = studio_store.get_org_settings(tenant_id=auth.tenant_id, org_id=target_org_id)
    onboarding = studio_store.get_org_onboarding(tenant_id=auth.tenant_id, org_id=target_org_id)
    return ok_response(
        request,
        data={
            "org_id": target_org_id,
            "organization": organization,
            "roles": ["owner", "admin", "member", "viewer"],
            "policy_modes": ["org_only", "cross_team", "open"],
            "settings": settings["settings"],
            "onboarding": onboarding,
        },
    )


@router.post("/invites")
def create_invite(request: Request, payload: StudioInviteCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    target_org_id = _resolve_target_org_id(request, auth.org_id, payload.org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)

    organization = studio_store.get_organization(tenant_id=auth.tenant_id, org_id=target_org_id)
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        )

    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
    invite = studio_store.create_org_invite(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        email=payload.email,
        role=payload.role,
        invited_by_user_id=auth.user_id,
        expires_at=expires_at,
    )
    return ok_response(request, data=invite)


@router.post("/invites/{invite_id}/accept")
def accept_invite(request: Request, invite_id: str, payload: StudioInviteAcceptPayload) -> dict[str, Any]:
    auth = require_authentication(request)

    invite = studio_store.get_org_invite(tenant_id=auth.tenant_id, invite_id=invite_id)
    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Invite not found.",
                "details": {"reason_code": "STUDIO_INVITE_NOT_FOUND"},
            },
        )

    target_org_id = payload.org_id or invite["org_id"]
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)

    if invite["org_id"] != target_org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invite does not match organization context.",
                "details": {"reason_code": "STUDIO_INVITE_ORG_MISMATCH"},
            },
        )

    if invite["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Invite is no longer pending.",
                "details": {"reason_code": "STUDIO_INVITE_NOT_PENDING"},
            },
        )

    expires_at = invite.get("expires_at")
    if isinstance(expires_at, str):
        expiry = datetime.fromisoformat(expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=410,
                detail={
                    "message": "Invite has expired.",
                    "details": {"reason_code": "STUDIO_INVITE_EXPIRED"},
                },
            )

    invitee = studio_store.get_user(tenant_id=auth.tenant_id, user_id=auth.user_id)
    if invitee is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "User not found.",
                "details": {"reason_code": "STUDIO_USER_NOT_FOUND"},
            },
        )

    if invitee["email"].lower() != str(invite["email"]).lower():
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Invite email does not match authenticated user.",
                "details": {"reason_code": "STUDIO_INVITE_EMAIL_MISMATCH"},
            },
        )

    existing = studio_store.get_membership_by_org_user(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        user_id=auth.user_id,
    )
    membership = (
        existing
        if existing is not None
        else studio_store.create_membership(
            tenant_id=auth.tenant_id,
            org_id=target_org_id,
            user_id=auth.user_id,
            role=invite["role"],
            status="active",
        )
    )

    accepted_invite = studio_store.accept_org_invite(
        tenant_id=auth.tenant_id,
        invite_id=invite_id,
        accepted_by_user_id=auth.user_id,
    )
    if accepted_invite is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Invite not found.",
                "details": {"reason_code": "STUDIO_INVITE_NOT_FOUND"},
            },
        )

    return ok_response(request, data={"invite": accepted_invite, "membership": membership})


@router.get("/onboarding/status")
def get_onboarding_status(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = _resolve_target_org_id(request, auth.org_id, org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    onboarding = studio_store.get_org_onboarding(tenant_id=auth.tenant_id, org_id=target_org_id)
    return ok_response(request, data=onboarding)


@router.post("/onboarding/complete")
def complete_onboarding(request: Request, payload: StudioOnboardingCompletePayload) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    target_org_id = _resolve_target_org_id(request, auth.org_id, payload.org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    onboarding = studio_store.complete_org_onboarding(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        completed_by_user_id=auth.user_id,
        checklist_patch=payload.checklist,
    )
    return ok_response(request, data=onboarding)


@router.get("/settings")
def get_settings(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = _resolve_target_org_id(request, auth.org_id, org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    settings = studio_store.get_org_settings(tenant_id=auth.tenant_id, org_id=target_org_id)
    return ok_response(request, data=settings)


@router.patch("/settings")
def patch_settings(request: Request, payload: StudioOrgSettingsPatchPayload) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    target_org_id = _resolve_target_org_id(request, auth.org_id, payload.org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    settings = studio_store.update_org_settings(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        patch=payload.settings,
        updated_by_user_id=auth.user_id,
    )
    return ok_response(request, data=settings)
