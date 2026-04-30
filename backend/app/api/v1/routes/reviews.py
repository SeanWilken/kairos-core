from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication, require_roles
from app.core.prompt_catalog_store import REQUIRED_REVIEW_CASES, prompt_catalog_store
from app.core.response import ok_response

router = APIRouter(prefix="/reviews", tags=["reviews"])


class PackConversationTestPayload(BaseModel):
    test_case_key: str = Field(min_length=1)
    prompt: str = ""
    response: str = ""
    passed: bool = False
    notes: str = ""


class PackReviewDecisionPayload(BaseModel):
    decision: Literal["approve", "request_changes", "reject"]
    review_notes: str = ""


class PackReviewNotesPayload(BaseModel):
    review_notes: str = ""


@router.get("/packs")
def list_pack_reviews(request: Request, status: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    items = prompt_catalog_store.list_review_queue(tenant_id=auth.tenant_id, status=status)
    return ok_response(request, data={"items": items})


@router.get("/packs/{queue_id}")
def get_pack_review(request: Request, queue_id: str) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    item = prompt_catalog_store.get_review_queue_entry(tenant_id=auth.tenant_id, queue_id=queue_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Pack review queue entry not found.",
                "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"},
            },
        )
    return ok_response(request, data=item)


@router.post("/packs/{queue_id}/conversation")
def submit_pack_review_conversation(
    request: Request,
    queue_id: str,
    payload: PackConversationTestPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    item = prompt_catalog_store.upsert_review_conversation_test(
        tenant_id=auth.tenant_id,
        queue_id=queue_id,
        test_case_key=payload.test_case_key,
        prompt=payload.prompt,
        response=payload.response,
        passed=payload.passed,
        notes=payload.notes,
        created_by_user_id=auth.user_id,
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Pack review queue entry not found.",
                "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"},
            },
        )
    return ok_response(
        request,
        data={
            "conversation_test": item,
            "required_cases": sorted(REQUIRED_REVIEW_CASES),
        },
    )


@router.post("/packs/{queue_id}/decision")
def decide_pack_review(
    request: Request,
    queue_id: str,
    payload: PackReviewDecisionPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    result = prompt_catalog_store.finalize_review_decision(
        tenant_id=auth.tenant_id,
        queue_id=queue_id,
        decision=payload.decision,
        review_notes=payload.review_notes,
        reviewed_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Pack review queue entry not found.",
                "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"},
            },
        )
    if "error" in result:
        error = result["error"]
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Pack review decision failed.",
                "details": error,
            },
        )
    return ok_response(request, data=result)


@router.post("/packs/{queue_id}/approve")
def approve_pack_review(
    request: Request,
    queue_id: str,
    payload: PackReviewNotesPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    result = prompt_catalog_store.finalize_review_decision(
        tenant_id=auth.tenant_id,
        queue_id=queue_id,
        decision="approve",
        review_notes=payload.review_notes,
        reviewed_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail={"message": "Pack review queue entry not found.", "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"}})
    if "error" in result:
        raise HTTPException(status_code=422, detail={"message": "Pack review decision failed.", "details": result["error"]})
    return ok_response(request, data=result)


@router.post("/packs/{queue_id}/reject")
def reject_pack_review(
    request: Request,
    queue_id: str,
    payload: PackReviewNotesPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    result = prompt_catalog_store.finalize_review_decision(
        tenant_id=auth.tenant_id,
        queue_id=queue_id,
        decision="reject",
        review_notes=payload.review_notes,
        reviewed_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail={"message": "Pack review queue entry not found.", "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"}})
    return ok_response(request, data=result)


@router.post("/packs/{queue_id}/request-changes")
def request_changes_pack_review(
    request: Request,
    queue_id: str,
    payload: PackReviewNotesPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    result = prompt_catalog_store.finalize_review_decision(
        tenant_id=auth.tenant_id,
        queue_id=queue_id,
        decision="request_changes",
        review_notes=payload.review_notes,
        reviewed_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail={"message": "Pack review queue entry not found.", "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"}})
    return ok_response(request, data=result)


@router.post("/packs/{queue_id}/install")
def install_approved_pack(request: Request, queue_id: str) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    result = prompt_catalog_store.install_approved_pack(
        tenant_id=auth.tenant_id,
        queue_id=queue_id,
        installed_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail={"message": "Pack review queue entry not found.", "details": {"reason_code": "PACK_REVIEW_NOT_FOUND"}})
    if "error" in result:
        raise HTTPException(status_code=422, detail={"message": "Pack install failed.", "details": result["error"]})
    return ok_response(request, data=result)
