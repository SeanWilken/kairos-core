from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication
from app.core.onboarding_store import onboarding_store
from app.core.response import ok_response

router = APIRouter(tags=["ingest"])


class IngestJobCreatePayload(BaseModel):
    session_id: str = Field(min_length=1)
    source_files: list[dict[str, str]] = Field(min_length=1)
    chunking_profile: str = Field(min_length=1)
    embedding_profile: str = Field(min_length=1)
    namespace: str = "tenant_default"


@router.post("/ingest/jobs")
def create_ingest_job(request: Request, payload: IngestJobCreatePayload) -> dict[str, Any]:
    require_authentication(request, require_org=True)

    session = onboarding_store.get_bootstrap_session(
        payload.session_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Bootstrap session not found for ingest.",
                "details": {"reason_code": "BOOTSTRAP_SESSION_NOT_FOUND"},
            },
        )

    status = onboarding_store.get_runtime_status(
        payload.session_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if status is None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Runtime checks must pass before ingest.",
                "details": {"reason_code": "RUNTIME_CHECKS_NOT_PASSED"},
            },
        )

    summary = status.get("summary", {})
    required_failed = int(summary.get("required_failed", 0))
    required_pending = int(summary.get("required_pending", 0))

    has_executed_checks = onboarding_store.has_runtime_check_run(
        payload.session_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if not has_executed_checks or required_failed > 0 or required_pending > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Runtime checks must pass before ingest.",
                "details": {"reason_code": "RUNTIME_CHECKS_NOT_PASSED"},
            },
        )

    job = onboarding_store.create_ingest_job(payload.model_dump())
    return ok_response(request, data=job)


@router.get("/ingest/jobs/{job_id}")
def get_ingest_job(request: Request, job_id: str) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    job = onboarding_store.get_ingest_job(
        job_id,
        tenant_id=request.state.tenant_id,
        org_id=request.state.org_id,
    )
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Ingest job not found.",
                "details": {"reason_code": "INGEST_JOB_NOT_FOUND"},
            },
        )
    return ok_response(request, data=job)
