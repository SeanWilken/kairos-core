from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication
from app.core.response import ok_response
from app.core.tool_execution_store import tool_execution_store
from app.core.tool_runtime import generate_image_tool, get_tool_provider_status, send_email_tool

router = APIRouter(prefix="/tools", tags=["tools"])


class ImageGeneratePayload(BaseModel):
    org_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    provider_id: str = Field(default="google")
    model_id: str = Field(default="imagen-3.0-generate-002")
    tool_id: str = Field(default="nano_banana")


class EmailSendPayload(BaseModel):
    org_id: str = Field(min_length=1)
    sender: str = Field(min_length=3)
    recipients: list[str] = Field(default_factory=list)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


@router.post("/image/generate")
def generate_image(request: Request, payload: ImageGeneratePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    output = generate_image_tool(
        prompt=payload.prompt,
        provider_id=payload.provider_id,
        model_id=payload.model_id,
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id=payload.tool_id,
        provider_id=str(output.get("provider_id", payload.provider_id)),
        model_id=str(output.get("model_id", payload.model_id)),
        input_payload={"prompt": payload.prompt},
        output_payload=output,
        created_by_user_id=auth.user_id,
        status=str(output.get("status", "completed")),
    )
    return ok_response(request, data=execution)


@router.get("/providers/status")
def get_providers_status(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(request, data=get_tool_provider_status())


@router.get("/executions")
def list_tool_executions(request: Request, org_id: str, limit: int = 50) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = tool_execution_store.list_executions(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        limit=max(1, min(limit, 200)),
    )
    return ok_response(request, data={"items": items})


@router.post("/email/send")
def send_email(request: Request, payload: EmailSendPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    send_result = send_email_tool(
        sender=payload.sender,
        recipients=payload.recipients,
        subject=payload.subject,
        body=payload.body,
    )
    message = tool_execution_store.create_email(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        sender=payload.sender,
        recipients=payload.recipients,
        subject=payload.subject,
        body=payload.body,
        created_by_user_id=auth.user_id,
        status=str(send_result.get("status", "sent")),
        metadata=send_result,
    )
    tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id="email_send",
        provider_id=str(send_result.get("provider_id", "email")),
        model_id="",
        input_payload={
            "sender": payload.sender,
            "recipients": payload.recipients,
            "subject": payload.subject,
        },
        output_payload={"email_id": message["email_id"], "status": message["status"], **send_result},
        created_by_user_id=auth.user_id,
        status=str(send_result.get("status", "completed")),
    )
    return ok_response(request, data={**message, "transport": send_result})


@router.get("/email/messages")
def list_email_messages(request: Request, org_id: str, limit: int = 50) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = tool_execution_store.list_emails(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        limit=max(1, min(limit, 200)),
    )
    return ok_response(request, data={"items": items})
