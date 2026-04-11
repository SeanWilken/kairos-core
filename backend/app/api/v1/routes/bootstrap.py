from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.onboarding_store import onboarding_store
from app.core.request_context import require_request_scope
from app.core.response import ok_response

router = APIRouter(tags=["bootstrap"])


class BootstrapSessionPayload(BaseModel):
    runtime: dict[str, Any] = Field(default_factory=dict)
    database: dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)
    vector: dict[str, Any] = Field(default_factory=dict)


class BootstrapSessionPatch(BaseModel):
    status: str | None = None
    runtime: dict[str, Any] | None = None
    database: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    vector: dict[str, Any] | None = None


@router.post("/bootstrap/sessions")
def create_bootstrap_session(request: Request, payload: BootstrapSessionPayload) -> dict[str, Any]:
    require_request_scope(request)
    session = onboarding_store.create_bootstrap_session(
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
        payload=payload.model_dump(),
    )
    return ok_response(request, data=session)


@router.get("/bootstrap/sessions")
def list_bootstrap_sessions(
    request: Request, latest: bool = Query(default=False)
) -> dict[str, Any]:
    require_request_scope(request)
    sessions = onboarding_store.list_bootstrap_sessions(
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if latest:
        return ok_response(request, data=sessions[0] if sessions else None)
    return ok_response(request, data=sessions)


@router.get("/bootstrap/sessions/{session_id}")
def get_bootstrap_session(request: Request, session_id: str) -> dict[str, Any]:
    require_request_scope(request)
    session = onboarding_store.get_bootstrap_session(
        session_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bootstrap session not found.",
                "details": {"reason_code": "BOOTSTRAP_SESSION_NOT_FOUND"},
            },
        )
    return ok_response(request, data=session)


@router.patch("/bootstrap/sessions/{session_id}")
def patch_bootstrap_session(
    request: Request, session_id: str, payload: BootstrapSessionPatch
) -> dict[str, Any]:
    require_request_scope(request)
    session = onboarding_store.update_bootstrap_session(
        session_id,
        payload.model_dump(exclude_none=True),
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bootstrap session not found.",
                "details": {"reason_code": "BOOTSTRAP_SESSION_NOT_FOUND"},
            },
        )
    return ok_response(request, data=session)
