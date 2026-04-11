from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.onboarding_store import onboarding_store
from app.core.request_context import require_request_scope
from app.core.response import ok_response

router = APIRouter(tags=["system"])


class RuntimeChecksRunPayload(BaseModel):
    session_id: str = Field(min_length=1)
    check_ids: list[str] = Field(default_factory=list)


@router.get("/system/status")
def get_system_status(request: Request, session_id: str) -> dict[str, Any]:
    require_request_scope(request)
    status = onboarding_store.get_runtime_status(
        session_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if status is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bootstrap session not found for runtime status.",
                "details": {"reason_code": "BOOTSTRAP_SESSION_NOT_FOUND"},
            },
        )
    return ok_response(request, data=status)


@router.post("/system/checks/run")
def run_system_checks(request: Request, payload: RuntimeChecksRunPayload) -> dict[str, Any]:
    require_request_scope(request)
    status = onboarding_store.run_runtime_checks(
        payload.session_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if status is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bootstrap session not found for runtime checks.",
                "details": {"reason_code": "BOOTSTRAP_SESSION_NOT_FOUND"},
            },
        )

    if payload.check_ids:
        selected = set(payload.check_ids)
        checks = [item for item in status["checks"] if item["check_id"] in selected]
        required_checks = [item for item in checks if item.get("required")]
        status = {
            **status,
            "checks": checks,
            "summary": {
                "required_passed": sum(
                    1 for item in required_checks if item.get("status") == "pass"
                ),
                "required_failed": sum(
                    1 for item in required_checks if item.get("status") == "fail"
                ),
                "required_pending": sum(
                    1 for item in required_checks if item.get("status") == "pending"
                ),
            },
        }

    return ok_response(request, data=status)
