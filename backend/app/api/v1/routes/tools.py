from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication
from app.core.collaboration_store import collaboration_store
from app.core.document_render_runtime import render_pdf_document
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.profile_presets import get_profile_preset, resolve_provider_preference
from app.core.response import ok_response
from app.core.tool_catalog import get_tool_catalog, get_tool_runtime_registry
from app.core.tool_execution_store import tool_execution_store
from app.core.tool_runtime import generate_image_tool, get_tool_provider_status, send_email_tool
from app.core.voice_runtime import synthesize_speech, transcribe_audio

router = APIRouter(prefix="/tools", tags=["tools"])


class ImageGeneratePayload(BaseModel):
    org_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    profile_id: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    tool_id: str = Field(default="nano_banana")


class EmailSendPayload(BaseModel):
    org_id: str = Field(min_length=1)
    sender: str = Field(min_length=3)
    recipients: list[str] = Field(default_factory=list)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


class SpeechSynthesizePayload(BaseModel):
    org_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    voice: str | None = None
    format: str = Field(default="wav")
    speed: float | None = None
    pitch: float | None = None
    gain_db: float | None = None
    tone: str | None = None
    cadence: str | None = None
    stability: float | None = None
    similarity_boost: float | None = None
    style: float | None = None


class DocumentDraftPayload(BaseModel):
    org_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    title: str = Field(default="Generated Draft")
    profile_id: str | None = None
    output_profile: str = Field(default="markdown_document")
    provider_id: str | None = None
    model_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class TaskCreateToolPayload(BaseModel):
    org_id: str = Field(min_length=1)
    title: str | None = None
    prompt: str = Field(min_length=1)
    description: str = ""
    profile_id: str | None = None
    visibility: str = Field(default="org_public")
    status: str = Field(default="todo")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    team_id: str | None = None
    channel_id: str | None = None


class WorkflowScaffoldPayload(BaseModel):
    org_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    profile_id: str | None = None
    output_profile: str = Field(default="walkthrough")
    provider_id: str | None = None
    model_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class PdfRenderPayload(BaseModel):
    org_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str | None = None
    prompt: str | None = None
    profile_id: str | None = None
    output_profile: str = Field(default="pdf_report")
    provider_id: str | None = None
    model_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


def _preferred_tool_policy(profile_id: str | None, tool_id: str) -> dict[str, Any] | None:
    profile = get_profile_preset(profile_id)
    if not isinstance(profile, dict):
        return None
    policies = profile.get("preferred_tool_policies", []) if isinstance(profile.get("preferred_tool_policies"), list) else []
    for item in policies:
        if not isinstance(item, dict):
            continue
        if str(item.get("tool_id", "")).strip() == tool_id:
            return item
    return None


@router.post("/image/generate")
def generate_image(request: Request, payload: ImageGeneratePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    provider_id, model_id = resolve_provider_preference(
        profile_id=payload.profile_id,
        capability="image_generation",
        provider_id=payload.provider_id,
        model_id=payload.model_id,
    )
    provider_id = provider_id or "google"
    model_id = model_id or "imagen-3.0-generate-002"
    output = generate_image_tool(
        prompt=payload.prompt,
        provider_id=provider_id,
        model_id=model_id,
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id=payload.tool_id,
        provider_id=str(output.get("provider_id", provider_id)),
        model_id=str(output.get("model_id", model_id)),
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


@router.get("/catalog")
def get_catalog(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(request, data=get_tool_catalog())


@router.get("/runtime-registry")
def get_runtime_registry(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(request, data=get_tool_runtime_registry())


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


@router.post("/speech/transcribe")
async def transcribe_speech(
    request: Request,
    org_id: str = Form(min_length=1),
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    audio = await file.read()
    result = transcribe_audio(audio_bytes=audio, filename=file.filename or "input.wav", language=language)
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        tool_id="speech_to_text",
        provider_id=str(result.get("provider", "speech_to_text")),
        model_id="",
        input_payload={"filename": file.filename or "input.wav", "language": language or ""},
        output_payload=result,
        created_by_user_id=auth.user_id,
        status="completed",
    )
    return ok_response(request, data={"execution": execution, **result})


@router.post("/speech/synthesize")
def synthesize_speech_tool(request: Request, payload: SpeechSynthesizePayload) -> Response:
    auth = require_authentication(request, require_org=True)
    audio, mime_type, filename = synthesize_speech(
        text=payload.text,
        voice=payload.voice,
        output_format=payload.format,
        speed=payload.speed,
        pitch=payload.pitch,
        gain_db=payload.gain_db,
        tone=payload.tone,
        cadence=payload.cadence,
        stability=payload.stability,
        similarity_boost=payload.similarity_boost,
        style=payload.style,
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id="text_to_speech",
        provider_id="tts",
        model_id="",
        input_payload={
            "text": payload.text,
            "voice": payload.voice or "",
            "format": payload.format,
            "speed": payload.speed,
            "pitch": payload.pitch,
            "gain_db": payload.gain_db,
            "tone": payload.tone or "",
            "cadence": payload.cadence or "",
            "stability": payload.stability,
            "similarity_boost": payload.similarity_boost,
            "style": payload.style,
        },
        output_payload={"filename": filename, "mime_type": mime_type, "size_bytes": len(audio)},
        created_by_user_id=auth.user_id,
        status="completed",
    )
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "X-Tool-Execution-Id": execution["execution_id"],
    }
    return Response(content=audio, media_type=mime_type, headers=headers)


@router.post("/documents/draft")
async def draft_document(request: Request, payload: DocumentDraftPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    profile = get_profile_preset(payload.profile_id)
    provider_id, model_id = resolve_provider_preference(
        profile_id=payload.profile_id,
        capability="document_drafting",
        provider_id=payload.provider_id,
        model_id=payload.model_id,
    )
    provider_id = provider_id or "anthropic"

    output_instructions = {
        "markdown_document": "Return a clean markdown document with title, sections, and short lists where useful.",
        "walkthrough": "Return a step-by-step walkthrough in markdown with numbered steps and validation notes.",
        "report": "Return a structured report in markdown with sections for summary, findings, risks, and next actions.",
        "summary": "Return a concise markdown summary with key bullets and next actions.",
        "task_bundle": "Return markdown that groups recommended tasks, priorities, and ownership notes.",
        "catalog": "Return a categorized markdown catalog with sections and short descriptions.",
    }
    output_instruction = output_instructions.get(payload.output_profile, output_instructions["markdown_document"])
    if profile and isinstance(profile, dict):
        preferred_outputs = profile.get("preferred_outputs", []) if isinstance(profile.get("preferred_outputs"), list) else []
    else:
        preferred_outputs = []

    context_text = json.dumps(payload.context, indent=2) if payload.context else "{}"
    result = await model_gateway.generate_text(
        ModelRequest(
            system_prompt=(
                "You are drafting structured content for MyAI tools. "
                f"{output_instruction} "
                f"Preferred outputs for this profile: {', '.join(str(item) for item in preferred_outputs) or 'unspecified'}."
            ),
            conversation_messages=[
                {
                    "role": "user",
                    "content": f"Title: {payload.title}\n\nPrompt: {payload.prompt}\n\nContext:\n{context_text}",
                }
            ],
            model_profile="balanced",
            provider_id=provider_id,
            model_id=model_id,
            tenant_id=auth.tenant_id,
            org_id=auth.org_id,
        )
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id="document_create_markdown",
        provider_id=provider_id,
        model_id=result.model,
        input_payload={
            "title": payload.title,
            "prompt": payload.prompt,
            "profile_id": payload.profile_id,
            "output_profile": payload.output_profile,
            "context": payload.context,
        },
        output_payload={"title": payload.title, "content": result.content, "usage": result.usage},
        created_by_user_id=auth.user_id,
        status="completed",
    )
    return ok_response(
        request,
        data={
            "title": payload.title,
            "profile_id": payload.profile_id,
            "output_profile": payload.output_profile,
            "provider_id": provider_id,
            "model_id": result.model,
            "content": result.content,
            "usage": result.usage,
            "execution": execution,
        },
    )


@router.post("/tasks/create")
def create_task_tool(request: Request, payload: TaskCreateToolPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    policy = _preferred_tool_policy(payload.profile_id, "task_create") or {}
    title = payload.title or payload.prompt.strip().splitlines()[0][:120] or "New Task"
    task = collaboration_store.create_task(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        owner_user_id=auth.user_id,
        title=title,
        description=payload.description or payload.prompt,
        visibility=payload.visibility,
        status=payload.status,
        team_id=payload.team_id,
        tags=payload.tags,
        metadata={
            **payload.metadata,
            "created_from": "tool_wrapper",
            "profile_id": payload.profile_id,
            "tool_policy": policy,
        },
        related_node_ids=[],
        channel_id=payload.channel_id,
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id="task_create",
        provider_id="core",
        model_id="",
        input_payload=payload.model_dump(),
        output_payload={"task": task},
        created_by_user_id=auth.user_id,
        status="completed",
    )
    return ok_response(request, data={"task": task, "execution": execution})


@router.post("/workflows/scaffold")
async def create_workflow_scaffold(request: Request, payload: WorkflowScaffoldPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    provider_id, model_id = resolve_provider_preference(
        profile_id=payload.profile_id,
        capability="document_drafting",
        provider_id=payload.provider_id,
        model_id=payload.model_id,
    )
    provider_id = provider_id or "anthropic"
    policy = _preferred_tool_policy(payload.profile_id, "workflow_create") or {}
    context_text = json.dumps(payload.context, indent=2) if payload.context else "{}"
    output_instruction = (
        "Return a markdown workflow scaffold with sections for objective, prerequisites, stages, tasks, risks, checkpoints, and next actions."
        if payload.output_profile == "walkthrough"
        else "Return a markdown workflow scaffold with grouped tasks and execution notes."
    )
    result = await model_gateway.generate_text(
        ModelRequest(
            system_prompt=(
                "You are generating a workflow scaffold for MyAI. "
                f"{output_instruction}"
            ),
            conversation_messages=[
                {
                    "role": "user",
                    "content": f"Title: {payload.title}\n\nPrompt: {payload.prompt}\n\nContext:\n{context_text}",
                }
            ],
            model_profile="balanced",
            provider_id=provider_id,
            model_id=model_id,
            tenant_id=auth.tenant_id,
            org_id=auth.org_id,
        )
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id="workflow_create",
        provider_id=provider_id,
        model_id=result.model,
        input_payload={**payload.model_dump(), "tool_policy": policy},
        output_payload={"title": payload.title, "content": result.content, "usage": result.usage},
        created_by_user_id=auth.user_id,
        status="completed",
    )
    return ok_response(
        request,
        data={
            "title": payload.title,
            "profile_id": payload.profile_id,
            "output_profile": payload.output_profile,
            "provider_id": provider_id,
            "model_id": result.model,
            "content": result.content,
            "usage": result.usage,
            "execution": execution,
        },
    )


@router.post("/documents/render-pdf")
async def render_pdf_tool(request: Request, payload: PdfRenderPayload) -> Response:
    auth = require_authentication(request, require_org=True)
    provider_id = None
    model_id = None
    content = payload.content or ""
    if not content.strip():
        if not payload.prompt or not payload.prompt.strip():
            raise ValueError("Either content or prompt is required to render a PDF document.")
        provider_id, model_id = resolve_provider_preference(
            profile_id=payload.profile_id,
            capability="document_drafting",
            provider_id=payload.provider_id,
            model_id=payload.model_id,
        )
        provider_id = provider_id or "anthropic"
        context_text = json.dumps(payload.context, indent=2) if payload.context else "{}"
        draft_result = await model_gateway.generate_text(
            ModelRequest(
                system_prompt=(
                    "You are generating a structured markdown report for later PDF rendering. "
                    "Return clear sections, short lists, and print-friendly formatting."
                ),
                conversation_messages=[
                    {
                        "role": "user",
                        "content": f"Title: {payload.title}\n\nPrompt: {payload.prompt}\n\nContext:\n{context_text}",
                    }
                ],
                model_profile="balanced",
                provider_id=provider_id,
                model_id=model_id,
                tenant_id=auth.tenant_id,
                org_id=auth.org_id,
            )
        )
        content = draft_result.content
        model_id = draft_result.model
    pdf_bytes, mime_type, filename = render_pdf_document(
        title=payload.title,
        content=content,
        command_template=str(os.getenv("MYAI_PDF_COMMAND_TEMPLATE", "")).strip(),
    )
    execution = tool_execution_store.create_execution(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        tool_id="pdf_generate",
        provider_id=provider_id or "command",
        model_id=model_id or "",
        input_payload=payload.model_dump(),
        output_payload={"filename": filename, "mime_type": mime_type, "size_bytes": len(pdf_bytes)},
        created_by_user_id=auth.user_id,
        status="completed",
    )
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "X-Tool-Execution-Id": execution["execution_id"],
    }
    return Response(content=pdf_bytes, media_type=mime_type, headers=headers)


@router.get("/email/messages")
def list_email_messages(request: Request, org_id: str, limit: int = 50) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = tool_execution_store.list_emails(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        limit=max(1, min(limit, 200)),
    )
    return ok_response(request, data={"items": items})
