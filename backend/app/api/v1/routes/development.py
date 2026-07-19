from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication
from app.core.development_capability_inventory import build_runner_capability_profile, build_workspace_capability_profile, resolve_capability_requirements
from app.core.response import ok_response
from app.core.suite_store import suite_store

router = APIRouter(prefix="/development", tags=["development"])


class CapabilityResolvePayload(BaseModel):
    workspace_id: str | None = None
    runner_id: str | None = None
    action_key: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    context: dict[str, object] = Field(default_factory=dict)


@router.get("/workspaces/{workspace_id}/capabilities")
def get_workspace_capabilities(request: Request, workspace_id: str) -> dict[str, object]:
    auth = require_authentication(request, require_org=True)
    workspace = suite_store.get_workspace(tenant_id=auth.tenant_id, workspace_id=workspace_id)
    if workspace is None or str(workspace.get("org_id", "")).strip() != str(auth.org_id or "").strip():
        raise HTTPException(
            status_code=404,
            detail={"message": "Workspace not found.", "details": {"reason_code": "WORKSPACE_NOT_FOUND"}},
        )
    profile = build_workspace_capability_profile(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        workspace=workspace,
    )
    return ok_response(request, data=profile)


@router.get("/runners/{runner_id}/capabilities")
def get_runner_capabilities(request: Request, runner_id: str) -> dict[str, object]:
    auth = require_authentication(request, require_org=True)
    workspaces = suite_store.list_workspaces(tenant_id=auth.tenant_id, org_id=auth.org_id or "", status="")
    profile = build_runner_capability_profile(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        runner_id=runner_id,
        workspaces=workspaces,
    )
    return ok_response(request, data=profile)


@router.post("/capabilities/resolve")
def resolve_capabilities(request: Request, payload: CapabilityResolvePayload) -> dict[str, object]:
    auth = require_authentication(request, require_org=True)
    required_capabilities = [*payload.required_capabilities]
    action_key = str(payload.action_key or "").strip()
    if action_key:
        required_capabilities.append(action_key)
    required_capabilities = [str(item).strip() for item in required_capabilities if str(item).strip()]
    if not required_capabilities:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "At least one capability is required.",
                "details": {"reason_code": "DEVELOPMENT_CAPABILITY_REQUIRED"},
            },
        )
    workspace = None
    profile: dict[str, object]
    if payload.workspace_id:
        workspace = suite_store.get_workspace(tenant_id=auth.tenant_id, workspace_id=payload.workspace_id)
        if workspace is None or str(workspace.get("org_id", "")).strip() != str(auth.org_id or "").strip():
            raise HTTPException(
                status_code=404,
                detail={"message": "Workspace not found.", "details": {"reason_code": "WORKSPACE_NOT_FOUND"}},
            )
        profile = build_workspace_capability_profile(
            tenant_id=auth.tenant_id,
            org_id=auth.org_id or "",
            user_id=auth.user_id,
            workspace=workspace,
        )
    elif payload.runner_id:
        workspaces = suite_store.list_workspaces(tenant_id=auth.tenant_id, org_id=auth.org_id or "", status="")
        profile = build_runner_capability_profile(
            tenant_id=auth.tenant_id,
            org_id=auth.org_id or "",
            user_id=auth.user_id,
            runner_id=payload.runner_id,
            workspaces=workspaces,
        )
    else:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "workspace_id or runner_id is required.",
                "details": {"reason_code": "DEVELOPMENT_SCOPE_REQUIRED"},
            },
        )
    resolution = resolve_capability_requirements(
        capability_profile=profile,
        required_capabilities=required_capabilities,
        workspace=workspace if isinstance(workspace, dict) else None,
    )
    return ok_response(
        request,
        data={
            "workspace_id": payload.workspace_id,
            "runner_id": payload.runner_id or profile.get("runnerId"),
            "action_key": action_key,
            "required_capabilities": required_capabilities,
            **resolution,
        },
    )
