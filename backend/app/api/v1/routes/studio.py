from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication, require_roles
from app.core.response import ok_response
from app.core.schemas import Envelope
from app.core.studio_store import studio_store
from app.core.tool_execution_store import tool_execution_store
from app.core.tool_runtime import send_email_tool

bearer_scheme = HTTPBearer(auto_error=False)


def _studio_bearer_doc(
    _: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    return None


StudioRole = Literal["owner", "admin", "member", "viewer"]
InviteStatus = Literal["pending", "accepted", "expired", "cancelled"]
OnboardingStatus = Literal["pending", "in_progress", "completed"]
PolicyMode = Literal["org_only", "cross_team", "open"]
SettingsKey = Literal[
    "invite_policy",
    "channel_policy",
    "task_visibility_default",
    "ai_response_policy",
    "prompt_policy_mode",
]


router = APIRouter(prefix="/studio", tags=["studio"], dependencies=[Depends(_studio_bearer_doc)])


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
    role: StudioRole = "member"
    status: str = "active"


class StudioMembershipPatchPayload(BaseModel):
    role: StudioRole | None = None
    status: str | None = None


class StudioInviteCreatePayload(BaseModel):
    org_id: str | None = None
    email: str = Field(min_length=3)
    role: StudioRole = "member"
    expires_in_days: int = Field(default=7, ge=1, le=30)


class StudioInviteAcceptPayload(BaseModel):
    org_id: str | None = Field(
        default=None,
        description="Optional org context override; must match invite org if provided.",
    )


class StudioOrgSettingsPatchPayload(BaseModel):
    org_id: str | None = None
    settings: dict[SettingsKey, str | bool | int] = Field(
        default_factory=dict,
        description=(
            "Merge patch semantics. Provided keys are merged into existing settings; "
            "omitted keys remain unchanged."
        ),
        examples=[{"invite_policy": "admin_only", "ai_response_policy": "single_best"}],
    )


class StudioOnboardingCompletePayload(BaseModel):
    org_id: str | None = None
    checklist: dict[str, bool] | None = None


class StudioErrorData(BaseModel):
    pass


class StudioGovernanceBaselineData(BaseModel):
    org_id: str
    organization: dict[str, Any]
    roles: list[StudioRole]
    policy_modes: list[PolicyMode]
    settings: dict[SettingsKey, str | bool | int]
    onboarding: dict[str, Any]


class StudioInviteData(BaseModel):
    invite_id: str
    tenant_id: str
    org_id: str
    email: str
    role: StudioRole
    status: InviteStatus
    invited_by_user_id: str | None
    accepted_by_user_id: str | None
    expires_at: str | None
    created_at: str
    updated_at: str


class StudioInviteAcceptData(BaseModel):
    invite: StudioInviteData
    membership: dict[str, Any]


class StudioOnboardingData(BaseModel):
    tenant_id: str
    org_id: str
    status: OnboardingStatus
    checklist: dict[str, bool]
    completed_by_user_id: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class StudioOrgSettingsData(BaseModel):
    setting_id: str
    tenant_id: str
    org_id: str
    settings: dict[SettingsKey, str | bool | int]
    updated_by_user_id: str | None
    created_at: str
    updated_at: str


StudioErrorEnvelope = Envelope[StudioErrorData]
_governance_common_responses = {
    401: {"model": StudioErrorEnvelope, "description": "Authentication required."},
    403: {"model": StudioErrorEnvelope, "description": "Organization scope forbidden."},
    422: {"model": StudioErrorEnvelope, "description": "Invalid request payload."},
}


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
    if not auth.is_global_admin and not auth.org_id and not auth.roles:
        # Allow first org bootstrap for tenant-scoped users before membership exists.
        pass
    else:
        require_roles(auth, {"owner", "admin"})
    organization = studio_store.create_organization(
        tenant_id=auth.tenant_id,
        name=payload.name,
        slug=payload.slug,
        mode=payload.mode,
        owner_user_id=payload.owner_user_id or auth.user_id,
    )
    existing_membership = studio_store.get_membership_by_org_user(
        tenant_id=auth.tenant_id,
        org_id=organization["org_id"],
        user_id=auth.user_id,
    )
    if existing_membership is None:
        studio_store.create_membership(
            tenant_id=auth.tenant_id,
            org_id=organization["org_id"],
            user_id=auth.user_id,
            role="owner",
            status="active",
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


@router.get(
    "/governance/baseline",
    response_model=Envelope[StudioGovernanceBaselineData],
    responses={
        **_governance_common_responses,
        404: {"model": StudioErrorEnvelope, "description": "Organization not found."},
    },
)
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


@router.post(
    "/invites",
    response_model=Envelope[StudioInviteData],
    responses={
        **_governance_common_responses,
        404: {"model": StudioErrorEnvelope, "description": "Organization not found."},
    },
)
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
    org_name = str(organization.get("name", "organization"))
    invite_link = f"{request.url.scheme}://{request.url.netloc}/invites/{invite['invite_id']}"
    subject = f"Invitation to join {org_name}"
    body = (
        f"You have been invited to join {org_name} as {invite['role']}.\n\n"
        f"Invite ID: {invite['invite_id']}\n"
        f"Expires: {invite.get('expires_at')}\n"
        f"Accept link: {invite_link}\n"
    )
    transport = send_email_tool(
        sender="noreply@myai.local",
        recipients=[invite["email"]],
        subject=subject,
        body=body,
    )
    email_message = tool_execution_store.create_email(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        sender="noreply@myai.local",
        recipients=[invite["email"]],
        subject=subject,
        body=body,
        created_by_user_id=auth.user_id,
        status=str(transport.get("status", "sent")),
        metadata=transport,
    )
    tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        tool_id="email_send",
        provider_id=str(transport.get("provider_id", "email")),
        model_id="",
        input_payload={
            "recipients": [invite["email"]],
            "subject": subject,
            "invite_id": invite["invite_id"],
        },
        output_payload={
            "email_id": email_message["email_id"],
            "status": email_message["status"],
            "transport": transport,
        },
        created_by_user_id=auth.user_id,
        status=str(transport.get("status", "completed")),
    )
    return ok_response(request, data=invite)


@router.post(
    "/invites/{invite_id}/accept",
    response_model=Envelope[StudioInviteAcceptData],
    responses={
        **_governance_common_responses,
        404: {"model": StudioErrorEnvelope, "description": "Invite or user not found."},
        409: {"model": StudioErrorEnvelope, "description": "Invite not in pending state."},
        410: {"model": StudioErrorEnvelope, "description": "Invite expired."},
    },
)
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


@router.get(
    "/onboarding/status",
    response_model=Envelope[StudioOnboardingData],
    responses=_governance_common_responses,
)
def get_onboarding_status(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = _resolve_target_org_id(request, auth.org_id, org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    onboarding = studio_store.get_org_onboarding(tenant_id=auth.tenant_id, org_id=target_org_id)
    return ok_response(request, data=onboarding)


@router.post(
    "/onboarding/complete",
    response_model=Envelope[StudioOnboardingData],
    responses=_governance_common_responses,
)
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


@router.get(
    "/settings",
    response_model=Envelope[StudioOrgSettingsData],
    responses=_governance_common_responses,
)
def get_settings(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    target_org_id = _resolve_target_org_id(request, auth.org_id, org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    settings = studio_store.get_org_settings(tenant_id=auth.tenant_id, org_id=target_org_id)
    return ok_response(request, data=settings)


@router.patch(
    "/settings",
    response_model=Envelope[StudioOrgSettingsData],
    responses=_governance_common_responses,
)
def patch_settings(request: Request, payload: StudioOrgSettingsPatchPayload) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    target_org_id = _resolve_target_org_id(request, auth.org_id, payload.org_id)
    _enforce_org_scope(auth.org_id, target_org_id, is_global_admin=auth.is_global_admin)
    try:
        settings = studio_store.update_org_settings(
            tenant_id=auth.tenant_id,
            org_id=target_org_id,
            patch=payload.settings,
            updated_by_user_id=auth.user_id,
        )
    except ValueError as error:
        if str(error) != "organization_not_found":
            raise
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        ) from error
    return ok_response(request, data=settings)
