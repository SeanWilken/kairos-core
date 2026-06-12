from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication
from app.core.audit_store import audit_store
from app.core.fallback_store import fallback_store
from app.core.onboarding_store import onboarding_store
from app.core.model_gateway_policy_store import model_gateway_policy_store
from app.core.prompt_template_store import prompt_template_store
from app.core.prompt_template_runtime import resolve_rendered_prompt_template
from app.core.resume_adapter_policy_store import resume_adapter_policy_store
from app.core.request_context import require_request_scope
from app.core.response import ok_response
from app.core.tool_provider_registry import get_ai_provider_catalog, get_provider_models

router = APIRouter(tags=["system"])


class RuntimeChecksRunPayload(BaseModel):
    session_id: str = Field(min_length=1)
    check_ids: list[str] = Field(default_factory=list)


class FallbackDecisionPayload(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")


class ResumeAdapterPolicyPayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(default="default", min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ResumeAdapterPolicyActivatePayload(BaseModel):
    org_id: str = Field(min_length=1)


class PromptTemplateVersionPayload(BaseModel):
    provider_id: str = Field(min_length=1)
    template_kind: str = Field(min_length=1)
    name: str = Field(default="default", min_length=1)
    content: str = Field(min_length=1)


class PromptTemplateActivatePayload(BaseModel):
    scope_level: str = Field(pattern="^(tenant|org|division|team)$")
    scope_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    template_kind: str = Field(min_length=1)
    template_version_id: str = Field(min_length=1)
    reason: str = ""


class ModelGatewayPolicyPayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(default="default", min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class PromptTemplateRenderPreviewPayload(BaseModel):
    provider_id: str = Field(min_length=1)
    template_kind: str = Field(min_length=1)
    org_id: str | None = None
    division_id: str | None = None
    team_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


PROMPT_TEMPLATE_RUNTIME_KINDS = ["system_prompt"]
PROMPT_TEMPLATE_EDITABLE_KINDS = [
    "system_prompt",
    "planner_prompt",
    "tool_call_prompt",
    "reflection_prompt",
    "focus_group_prompt",
    "tasking_prompt",
]


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
    require_authentication(request, require_org=True)
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


@router.get("/system/ai/providers")
def get_ai_provider_status(request: Request) -> dict[str, Any]:
    require_authentication(request)
    return ok_response(request, data=get_ai_provider_catalog())


@router.get("/system/ai/providers/{provider_id}/models")
def get_ai_provider_models(
    request: Request,
    provider_id: str,
    capability: str | None = None,
) -> dict[str, Any]:
    require_authentication(request)
    result = get_provider_models(provider_id=provider_id, capability=capability)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Provider not found.",
                "details": {"reason_code": "AI_PROVIDER_NOT_FOUND", "provider_id": provider_id},
            },
        )
    return ok_response(request, data=result)


@router.get("/system/audit/events")
def list_audit_events(
    request: Request,
    room_id: str | None = None,
    orchestration_run_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    auth = require_authentication(request)
    items = audit_store.list_events(
        tenant_id=auth.tenant_id,
        room_id=room_id,
        orchestration_run_id=orchestration_run_id,
        limit=max(1, min(limit, 500)),
    )
    return ok_response(request, data={"items": items})


@router.get("/system/fallback-approvals")
def list_fallback_approvals(
    request: Request,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    auth = require_authentication(request)
    items = fallback_store.list_requests(
        tenant_id=auth.tenant_id,
        status=status,
        limit=max(1, min(limit, 500)),
    )
    return ok_response(request, data={"items": items})


@router.post("/system/fallback-approvals/{request_id}/decision")
def decide_fallback_approval(
    request: Request,
    request_id: str,
    payload: FallbackDecisionPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    result = fallback_store.resolve_request(
        tenant_id=auth.tenant_id,
        request_id=request_id,
        decision=payload.decision,
        resolved_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Fallback approval request not found.",
                "details": {"reason_code": "FALLBACK_REQUEST_NOT_FOUND"},
            },
        )
    return ok_response(request, data=result)


@router.get("/system/resume-adapter-policies")
def list_resume_adapter_policies(
    request: Request,
    org_id: str,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Organization scope forbidden.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )
    items = resume_adapter_policy_store.list_policies(tenant_id=auth.tenant_id, org_id=org_id)
    return ok_response(request, data={"items": items})


@router.post("/system/resume-adapter-policies")
def create_resume_adapter_policy(request: Request, payload: ResumeAdapterPolicyPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and payload.org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Organization scope forbidden.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )
    created = resume_adapter_policy_store.create_policy(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        config=payload.config,
        created_by_user_id=auth.user_id,
        status="draft",
    )
    return ok_response(request, data=created)


@router.post("/system/resume-adapter-policies/{policy_id}/activate")
def activate_resume_adapter_policy(
    request: Request,
    policy_id: str,
    payload: ResumeAdapterPolicyActivatePayload,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and payload.org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Organization scope forbidden.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )
    result = resume_adapter_policy_store.activate_policy(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        policy_id=policy_id,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Resume adapter policy not found.",
                "details": {"reason_code": "RESUME_ADAPTER_POLICY_NOT_FOUND"},
            },
        )
    return ok_response(request, data=result)


@router.post("/system/resume-adapter-policies/{policy_id}/rollback")
def rollback_resume_adapter_policy(
    request: Request,
    policy_id: str,
    payload: ResumeAdapterPolicyActivatePayload,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and payload.org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Organization scope forbidden.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )
    result = resume_adapter_policy_store.rollback_to_policy(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        policy_id=policy_id,
        created_by_user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Resume adapter policy not found.",
                "details": {"reason_code": "RESUME_ADAPTER_POLICY_NOT_FOUND"},
            },
        )
    return ok_response(request, data=result)


@router.get("/system/prompt-templates/versions")
def list_prompt_template_versions(
    request: Request,
    provider_id: str | None = None,
    template_kind: str | None = None,
) -> dict[str, Any]:
    auth = require_authentication(request)
    items = prompt_template_store.list_versions(
        tenant_id=auth.tenant_id,
        provider_id=provider_id,
        template_kind=template_kind,
    )
    return ok_response(request, data={"items": items})


@router.post("/system/prompt-templates/versions")
def create_prompt_template_version(request: Request, payload: PromptTemplateVersionPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = prompt_template_store.create_version(
        tenant_id=auth.tenant_id,
        provider_id=payload.provider_id.strip().lower(),
        template_kind=payload.template_kind.strip(),
        name=payload.name.strip(),
        content=payload.content,
        created_by_user_id=auth.user_id,
    )
    return ok_response(request, data=item)


@router.post("/system/prompt-templates/activations")
def activate_prompt_template(request: Request, payload: PromptTemplateActivatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = prompt_template_store.activate(
        tenant_id=auth.tenant_id,
        scope_level=payload.scope_level,
        scope_id=payload.scope_id,
        provider_id=payload.provider_id.strip().lower(),
        template_kind=payload.template_kind.strip(),
        template_version_id=payload.template_version_id,
        reason=payload.reason,
        created_by_user_id=auth.user_id,
    )
    return ok_response(request, data=item)


@router.post("/system/prompt-templates/activations/{activation_id}/rollback")
def rollback_prompt_template_activation(request: Request, activation_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = prompt_template_store.rollback(
        tenant_id=auth.tenant_id,
        activation_id=activation_id,
        created_by_user_id=auth.user_id,
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Prompt template activation not found.",
                "details": {"reason_code": "PROMPT_TEMPLATE_ACTIVATION_NOT_FOUND"},
            },
        )
    return ok_response(request, data=item)


@router.get("/system/prompt-templates/resolve")
def resolve_prompt_template(
    request: Request,
    provider_id: str,
    template_kind: str,
    org_id: str | None = None,
    division_id: str | None = None,
    team_id: str | None = None,
) -> dict[str, Any]:
    auth = require_authentication(request)
    item = prompt_template_store.resolve_template(
        tenant_id=auth.tenant_id,
        provider_id=provider_id.strip().lower(),
        template_kind=template_kind,
        scopes={
            "team": team_id or "",
            "division": division_id or "",
            "org": org_id or (auth.org_id or ""),
            "tenant": auth.tenant_id,
        },
    )
    return ok_response(request, data=item or {})


@router.get("/system/prompt-templates/capabilities")
def get_prompt_template_capabilities(request: Request) -> dict[str, Any]:
    require_authentication(request)
    catalog = get_ai_provider_catalog()
    providers = [
        {
            "provider_id": str(item.get("provider_id", "")),
            "configured": bool(item.get("configured", False)),
            "default_chat_model": str((item.get("default_models", {}) or {}).get("chat", "")),
        }
        for item in catalog.get("providers", [])
        if isinstance(item, dict)
    ]
    return ok_response(
        request,
        data={
            "providers": providers,
            "runtime_supported_template_kinds": PROMPT_TEMPLATE_RUNTIME_KINDS,
            "editable_template_kinds": PROMPT_TEMPLATE_EDITABLE_KINDS,
            "scope_levels": ["tenant", "org", "division", "team"],
        },
    )


@router.post("/system/prompt-templates/render-preview")
def render_prompt_template_preview(
    request: Request,
    payload: PromptTemplateRenderPreviewPayload,
) -> dict[str, Any]:
    auth = require_authentication(request)
    rendered = resolve_rendered_prompt_template(
        tenant_id=auth.tenant_id,
        provider_id=payload.provider_id.strip().lower(),
        template_kind=payload.template_kind.strip(),
        scopes={
            "team": str(payload.team_id or ""),
            "division": str(payload.division_id or ""),
            "org": str(payload.org_id or auth.org_id or ""),
            "tenant": auth.tenant_id,
        },
        context=payload.context,
    )
    return ok_response(request, data={"rendered": rendered})


@router.get("/system/model-gateway-policies")
def list_model_gateway_policies(request: Request, org_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={"message": "Organization scope forbidden.", "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"}},
        )
    items = model_gateway_policy_store.list_policies(tenant_id=auth.tenant_id, org_id=org_id)
    return ok_response(request, data={"items": items})


@router.post("/system/model-gateway-policies")
def create_model_gateway_policy(request: Request, payload: ModelGatewayPolicyPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and payload.org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={"message": "Organization scope forbidden.", "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"}},
        )
    item = model_gateway_policy_store.create_policy(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        config=payload.config,
        created_by_user_id=auth.user_id,
    )
    return ok_response(request, data=item)


@router.post("/system/model-gateway-policies/{policy_id}/activate")
def activate_model_gateway_policy(request: Request, policy_id: str, payload: ResumeAdapterPolicyActivatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and payload.org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={"message": "Organization scope forbidden.", "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"}},
        )
    item = model_gateway_policy_store.activate_policy(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        policy_id=policy_id,
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Model gateway policy not found.", "details": {"reason_code": "MODEL_GATEWAY_POLICY_NOT_FOUND"}},
        )
    return ok_response(request, data=item)


@router.post("/system/model-gateway-policies/{policy_id}/rollback")
def rollback_model_gateway_policy(request: Request, policy_id: str, payload: ResumeAdapterPolicyActivatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.is_global_admin and payload.org_id != (auth.org_id or ""):
        raise HTTPException(
            status_code=403,
            detail={"message": "Organization scope forbidden.", "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"}},
        )
    item = model_gateway_policy_store.rollback_to_policy(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        policy_id=policy_id,
        created_by_user_id=auth.user_id,
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Model gateway policy not found.", "details": {"reason_code": "MODEL_GATEWAY_POLICY_NOT_FOUND"}},
        )
    return ok_response(request, data=item)
