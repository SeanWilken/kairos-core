from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.auth_context import AuthContext, require_authentication, require_roles
from app.core.collaboration_store import collaboration_store
from app.core.response import ok_response
from app.core.studio_store import studio_store

router = APIRouter(prefix="/studio", tags=["studio-collaboration"])


class DivisionCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str = ""


class TeamCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str = ""
    access_mode: str = Field(default="internal")
    division_id: str | None = None
    parent_team_id: str | None = None


class TeamMembershipCreatePayload(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(default="member")
    status: str = Field(default="active")


class TeamMembershipPatchPayload(BaseModel):
    role: str | None = None
    status: str | None = None


class ChannelCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    channel_type: str = Field(default="team")
    name: str = Field(min_length=1)
    team_id: str | None = None
    participant_user_ids: list[str] = Field(default_factory=list)
    retention_days: int = Field(default=90, ge=1, le=3650)
    response_policy: str = Field(default="single_best")
    auto_respond: bool = True
    responder_delay_seconds: int = Field(default=12, ge=0, le=120)
    default_persona_id: str | None = None


class ChannelMessageCreatePayload(BaseModel):
    content: str = Field(min_length=1)


class TaskCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    team_id: str | None = None
    visibility: str = Field(default="team_public")
    status: str = Field(default="todo")


class TaskPatchPayload(BaseModel):
    title: str | None = None
    description: str | None = None
    team_id: str | None = None
    visibility: str | None = None
    status: str | None = None


class TaskAssignmentCreatePayload(BaseModel):
    assignee_user_id: str = Field(min_length=1)
    status: str = "active"


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


def _require_org_exists(tenant_id: str, org_id: str) -> None:
    org = studio_store.get_organization(tenant_id=tenant_id, org_id=org_id)
    if org is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Organization not found.",
                "details": {"reason_code": "STUDIO_ORG_NOT_FOUND"},
            },
        )


def _can_access_task(auth: AuthContext, task: dict[str, Any]) -> bool:
    if auth.is_global_admin:
        return True
    if not auth.org_id or auth.org_id != task["org_id"]:
        return False

    visibility = task["visibility"]
    if visibility == "private_owner":
        return task.get("owner_user_id") == auth.user_id
    if visibility == "org_public":
        return True
    if visibility == "team_public":
        team_id = task.get("team_id")
        if not team_id:
            return False
        return collaboration_store.is_user_in_team(
            tenant_id=auth.tenant_id,
            team_id=team_id,
            user_id=auth.user_id,
        )
    return False


@router.post("/divisions")
def create_division(request: Request, payload: DivisionCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    _enforce_org_scope(auth, payload.org_id)
    _require_org_exists(auth.tenant_id, payload.org_id)

    division = collaboration_store.create_division(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
    )
    return ok_response(request, data=division)


@router.get("/divisions")
def list_divisions(request: Request, org_id: str = Query(min_length=1)) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, org_id)
    _require_org_exists(auth.tenant_id, org_id)
    items = collaboration_store.list_divisions(tenant_id=auth.tenant_id, org_id=org_id)
    return ok_response(request, data={"items": items})


@router.post("/teams")
def create_team(request: Request, payload: TeamCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    _enforce_org_scope(auth, payload.org_id)
    _require_org_exists(auth.tenant_id, payload.org_id)

    if payload.division_id is not None:
        division = collaboration_store.get_division(
            tenant_id=auth.tenant_id,
            division_id=payload.division_id,
        )
        if division is None or division["org_id"] != payload.org_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Division not found in organization.",
                    "details": {"reason_code": "STUDIO_DIVISION_NOT_FOUND"},
                },
            )

    if payload.parent_team_id is not None:
        parent = collaboration_store.get_team(tenant_id=auth.tenant_id, team_id=payload.parent_team_id)
        if parent is None or parent["org_id"] != payload.org_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Parent team not found in organization.",
                    "details": {"reason_code": "STUDIO_TEAM_NOT_FOUND"},
                },
            )

    team = collaboration_store.create_team(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        access_mode=payload.access_mode,
        division_id=payload.division_id,
        parent_team_id=payload.parent_team_id,
    )
    return ok_response(request, data=team)


@router.get("/teams")
def list_teams(
    request: Request,
    org_id: str = Query(min_length=1),
    division_id: str | None = Query(default=None),
    parent_team_id: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, org_id)
    _require_org_exists(auth.tenant_id, org_id)
    items = collaboration_store.list_teams(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        division_id=division_id,
        parent_team_id=parent_team_id,
    )
    return ok_response(request, data={"items": items})


@router.post("/teams/{team_id}/memberships")
def create_team_membership(
    request: Request, team_id: str, payload: TeamMembershipCreatePayload
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    team = collaboration_store.get_team(tenant_id=auth.tenant_id, team_id=team_id)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Team not found.", "details": {"reason_code": "STUDIO_TEAM_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, team["org_id"])

    user = studio_store.get_user(tenant_id=auth.tenant_id, user_id=payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "User not found.", "details": {"reason_code": "STUDIO_USER_NOT_FOUND"}},
        )

    existing = collaboration_store.get_team_membership_by_team_user(
        tenant_id=auth.tenant_id,
        team_id=team_id,
        user_id=payload.user_id,
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Team membership already exists.",
                "details": {"reason_code": "STUDIO_TEAM_MEMBERSHIP_EXISTS"},
            },
        )

    membership = collaboration_store.create_team_membership(
        tenant_id=auth.tenant_id,
        team_id=team_id,
        user_id=payload.user_id,
        role=payload.role,
        status=payload.status,
    )
    return ok_response(request, data=membership)


@router.get("/teams/{team_id}/memberships")
def list_team_memberships(request: Request, team_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    team = collaboration_store.get_team(tenant_id=auth.tenant_id, team_id=team_id)
    if team is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Team not found.", "details": {"reason_code": "STUDIO_TEAM_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, team["org_id"])
    items = collaboration_store.list_team_memberships(tenant_id=auth.tenant_id, team_id=team_id)
    return ok_response(request, data={"items": items})


@router.patch("/team-memberships/{team_membership_id}")
def patch_team_membership(
    request: Request, team_membership_id: str, payload: TeamMembershipPatchPayload
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})

    if payload.role is None and payload.status is None:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "At least one field must be provided.",
                "details": {"reason_code": "STUDIO_TEAM_MEMBERSHIP_PATCH_EMPTY"},
            },
        )

    updated = collaboration_store.update_team_membership(
        tenant_id=auth.tenant_id,
        team_membership_id=team_membership_id,
        role=payload.role,
        status=payload.status,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Team membership not found.",
                "details": {"reason_code": "STUDIO_TEAM_MEMBERSHIP_NOT_FOUND"},
            },
        )

    team = collaboration_store.get_team(tenant_id=auth.tenant_id, team_id=updated["team_id"])
    if team is not None:
        _enforce_org_scope(auth, team["org_id"])
    return ok_response(request, data=updated)


@router.post("/channels")
def create_channel(request: Request, payload: ChannelCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, payload.org_id)
    _require_org_exists(auth.tenant_id, payload.org_id)

    if payload.channel_type in {"team", "org"}:
        require_roles(auth, {"owner", "admin"})

    if payload.channel_type == "team":
        if payload.team_id is None:
            raise HTTPException(
                status_code=422,
                detail={"message": "team_id is required for team channels.", "details": {"reason_code": "TEAM_ID_REQUIRED"}},
            )
        team = collaboration_store.get_team(tenant_id=auth.tenant_id, team_id=payload.team_id)
        if team is None or team["org_id"] != payload.org_id:
            raise HTTPException(
                status_code=404,
                detail={"message": "Team not found.", "details": {"reason_code": "STUDIO_TEAM_NOT_FOUND"}},
            )

    channel = collaboration_store.create_channel(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        channel_type=payload.channel_type,
        name=payload.name,
        created_by_user_id=auth.user_id,
        retention_days=payload.retention_days,
        participant_user_ids=payload.participant_user_ids,
        team_id=payload.team_id,
        response_policy=payload.response_policy,
        auto_respond=payload.auto_respond,
        responder_delay_seconds=payload.responder_delay_seconds,
        default_persona_id=payload.default_persona_id,
    )
    return ok_response(request, data=channel)


@router.get("/channels")
def list_channels(
    request: Request,
    org_id: str = Query(min_length=1),
    channel_type: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, org_id)
    items = collaboration_store.list_channels(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        user_id=auth.user_id,
        channel_type=channel_type,
        team_id=team_id,
    )
    return ok_response(request, data={"items": items})


@router.post("/channels/{channel_id}/messages")
def create_channel_message(
    request: Request, channel_id: str, payload: ChannelMessageCreatePayload
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Channel not found.", "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, channel["org_id"])
    if not collaboration_store.is_channel_participant(
        tenant_id=auth.tenant_id, channel_id=channel_id, user_id=auth.user_id
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Channel access denied.",
                "details": {"reason_code": "STUDIO_CHANNEL_ACCESS_DENIED"},
            },
        )
    message = collaboration_store.create_channel_message(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        sender_user_id=auth.user_id,
        content=payload.content,
    )
    return ok_response(request, data=message)


@router.get("/channels/{channel_id}/messages")
def list_channel_messages(
    request: Request, channel_id: str, limit: int = Query(default=100, ge=1, le=500)
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    channel = collaboration_store.get_channel(tenant_id=auth.tenant_id, channel_id=channel_id)
    if channel is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Channel not found.", "details": {"reason_code": "STUDIO_CHANNEL_NOT_FOUND"}},
        )
    _enforce_org_scope(auth, channel["org_id"])
    if not collaboration_store.is_channel_participant(
        tenant_id=auth.tenant_id, channel_id=channel_id, user_id=auth.user_id
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Channel access denied.",
                "details": {"reason_code": "STUDIO_CHANNEL_ACCESS_DENIED"},
            },
        )
    items = collaboration_store.list_channel_messages(
        tenant_id=auth.tenant_id,
        channel_id=channel_id,
        limit=limit,
    )
    return ok_response(request, data={"items": items})


@router.post("/tasks")
def create_task(request: Request, payload: TaskCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, payload.org_id)
    _require_org_exists(auth.tenant_id, payload.org_id)

    if payload.visibility not in {"private_owner", "team_public", "org_public"}:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Task visibility is invalid.",
                "details": {"reason_code": "TASK_VISIBILITY_INVALID"},
            },
        )

    if payload.visibility == "team_public" and not payload.team_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "team_id is required for team_public tasks.",
                "details": {"reason_code": "TEAM_ID_REQUIRED"},
            },
        )

    if payload.team_id:
        team = collaboration_store.get_team(tenant_id=auth.tenant_id, team_id=payload.team_id)
        if team is None or team["org_id"] != payload.org_id:
            raise HTTPException(
                status_code=404,
                detail={"message": "Team not found.", "details": {"reason_code": "STUDIO_TEAM_NOT_FOUND"}},
            )

    task = collaboration_store.create_task(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        owner_user_id=auth.user_id,
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
        status=payload.status,
        team_id=payload.team_id,
    )
    return ok_response(request, data=task)


@router.get("/tasks")
def list_tasks(
    request: Request,
    org_id: str = Query(min_length=1),
    team_id: str | None = Query(default=None),
    assignee_user_id: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth, org_id)
    items = collaboration_store.list_tasks(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        team_id=team_id,
        assignee_user_id=assignee_user_id,
        visibility=visibility,
    )
    filtered = [item for item in items if _can_access_task(auth, item)]
    return ok_response(request, data={"items": filtered})


@router.get("/tasks/{task_id}")
def get_task(request: Request, task_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    task = collaboration_store.get_task(tenant_id=auth.tenant_id, task_id=task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Task not found.", "details": {"reason_code": "STUDIO_TASK_NOT_FOUND"}},
        )
    if not _can_access_task(auth, task):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Task access denied.",
                "details": {"reason_code": "STUDIO_TASK_ACCESS_DENIED"},
            },
        )
    return ok_response(request, data=task)


@router.patch("/tasks/{task_id}")
def patch_task(request: Request, task_id: str, payload: TaskPatchPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    existing = collaboration_store.get_task(tenant_id=auth.tenant_id, task_id=task_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Task not found.", "details": {"reason_code": "STUDIO_TASK_NOT_FOUND"}},
        )

    if existing.get("owner_user_id") != auth.user_id and not auth.is_global_admin:
        require_roles(auth, {"owner", "admin"})
        _enforce_org_scope(auth, existing["org_id"])

    if payload.visibility == "team_public" and (payload.team_id is None and existing.get("team_id") is None):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "team_id is required for team_public tasks.",
                "details": {"reason_code": "TEAM_ID_REQUIRED"},
            },
        )

    updated = collaboration_store.update_task(
        tenant_id=auth.tenant_id,
        task_id=task_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        visibility=payload.visibility,
        team_id=payload.team_id,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Task not found.", "details": {"reason_code": "STUDIO_TASK_NOT_FOUND"}},
        )
    return ok_response(request, data=updated)


@router.post("/tasks/{task_id}/assignments")
def create_task_assignment(
    request: Request, task_id: str, payload: TaskAssignmentCreatePayload
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    task = collaboration_store.get_task(tenant_id=auth.tenant_id, task_id=task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Task not found.", "details": {"reason_code": "STUDIO_TASK_NOT_FOUND"}},
        )
    if not _can_access_task(auth, task):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Task access denied.",
                "details": {"reason_code": "STUDIO_TASK_ACCESS_DENIED"},
            },
        )

    assignee = studio_store.get_user(tenant_id=auth.tenant_id, user_id=payload.assignee_user_id)
    if assignee is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "User not found.", "details": {"reason_code": "STUDIO_USER_NOT_FOUND"}},
        )

    existing = collaboration_store.get_task_assignment_by_task_user(
        tenant_id=auth.tenant_id,
        task_id=task_id,
        assignee_user_id=payload.assignee_user_id,
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Task assignment already exists.",
                "details": {"reason_code": "STUDIO_TASK_ASSIGNMENT_EXISTS"},
            },
        )

    assignment = collaboration_store.create_task_assignment(
        tenant_id=auth.tenant_id,
        task_id=task_id,
        assignee_user_id=payload.assignee_user_id,
        status=payload.status,
    )
    return ok_response(request, data=assignment)
