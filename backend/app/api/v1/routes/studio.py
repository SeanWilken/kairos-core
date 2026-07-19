from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.artifact_rules import evaluate_artifact_rules
from app.core.auth_context import require_authentication, require_roles
from app.core.collaboration_store import collaboration_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.response import ok_response
from app.core.schemas import Envelope
from app.core.studio_store import studio_store
from app.core.tool_execution_store import tool_execution_store
from app.core.tool_runtime import send_email_tool
from app.core.workflow_store import workflow_store
from app.core.knowledge_contract_store import knowledge_contract_store
from app.core.profile_presets import resolve_provider_preference

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


class WorkflowCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    trigger: dict[str, Any] = Field(default_factory=dict)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    logic_rules: list[dict[str, Any]] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    spec_version: str = "v0.3"


class WorkflowPatchPayload(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger: dict[str, Any] | None = None
    nodes: list[dict[str, Any]] | None = None
    edges: list[dict[str, Any]] | None = None
    logic_rules: list[dict[str, Any]] | None = None
    policy: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class WorkflowDryRunPayload(BaseModel):
    artifact: dict[str, Any] = Field(default_factory=dict)
    review_context: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunStartPayload(BaseModel):
    artifact: dict[str, Any] = Field(default_factory=dict)
    review_context: dict[str, Any] = Field(default_factory=dict)
    start_node_id: str | None = None


class WorkflowRunResumePayload(BaseModel):
    artifact: dict[str, Any] | None = None
    review_context: dict[str, Any] = Field(default_factory=dict)


class WorkflowReviewDecisionPayload(BaseModel):
    decision: str = Field(pattern="^(approve|reject|return_for_edit)$")


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


def _validate_workflow_graph(*, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], logic_rules: list[dict[str, Any]]) -> None:
    node_ids = {str(item.get("node_id", "")).strip() for item in nodes if isinstance(item, dict) and str(item.get("node_id", "")).strip()}
    if not node_ids:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Workflow must contain at least one node.",
                "details": {"reason_code": "WORKFLOW_NODE_REQUIRED"},
            },
        )
    rule_ids = {str(item.get("rule_id", "")).strip() for item in logic_rules if isinstance(item, dict) and str(item.get("rule_id", "")).strip()}
    for item in edges:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=422,
                detail={"message": "Workflow edge is invalid.", "details": {"reason_code": "WORKFLOW_EDGE_INVALID"}},
            )
        from_node_id = str(item.get("from_node_id", "")).strip()
        to_node_id = str(item.get("to_node_id", "")).strip()
        if not from_node_id or not to_node_id or from_node_id not in node_ids or to_node_id not in node_ids:
            raise HTTPException(
                status_code=422,
                detail={"message": "Workflow edge references missing node.", "details": {"reason_code": "WORKFLOW_EDGE_NODE_MISSING"}},
            )
        condition_ref = str(item.get("condition_ref", "")).strip()
        if condition_ref and condition_ref not in rule_ids:
            raise HTTPException(
                status_code=422,
                detail={"message": "Workflow edge references missing rule.", "details": {"reason_code": "WORKFLOW_EDGE_RULE_MISSING"}},
            )


def _resolve_start_node_id(*, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], requested_start_node_id: str | None) -> str:
    requested = str(requested_start_node_id or "").strip()
    node_ids = [str(item.get("node_id", "")).strip() for item in nodes if isinstance(item, dict) and str(item.get("node_id", "")).strip()]
    if requested:
        if requested not in node_ids:
            raise HTTPException(
                status_code=422,
                detail={"message": "Workflow start node not found.", "details": {"reason_code": "WORKFLOW_START_NODE_NOT_FOUND"}},
            )
        return requested
    inbound = {
        str(item.get("to_node_id", "")).strip()
        for item in edges
        if isinstance(item, dict) and str(item.get("to_node_id", "")).strip()
    }
    for node_id in node_ids:
        if node_id not in inbound:
            return node_id
    return node_ids[0]


def _node_map(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("node_id", "")).strip(): item
        for item in nodes
        if isinstance(item, dict) and str(item.get("node_id", "")).strip()
    }


def _edge_map(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for item in edges:
        if not isinstance(item, dict):
            continue
        from_node_id = str(item.get("from_node_id", "")).strip()
        if not from_node_id:
            continue
        adjacency.setdefault(from_node_id, []).append(item)
    return adjacency


def _next_node_from_edges(adjacency: dict[str, list[dict[str, Any]]], node_id: str) -> str | None:
    candidates = adjacency.get(node_id, [])
    for relationship_type in ("next", "success", "approved", "true_branch"):
        for item in candidates:
            if str(item.get("relationship_type", "")).strip() == relationship_type:
                target = str(item.get("to_node_id", "")).strip()
                if target:
                    return target
    if candidates:
        target = str(candidates[0].get("to_node_id", "")).strip()
        return target or None
    return None


def _build_workflow_artifact(
    *,
    title: str,
    subtype: str,
    content: str,
    created_by_user_id: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "entity_id": str(uuid4()),
        "kind": "knowledge_node",
        "kind_schema_version": "v1",
        "title": title,
        "summary": content[:240],
        "tags": [subtype],
        "contexts": [],
        "facets": {"subtype": subtype},
        "owners": [{"owner_type": "user", "owner_id": created_by_user_id}],
        "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
        "source": {
            "source_system": "workflow_execution",
            "source_id": subtype,
            "external_ref": "",
            "source_of_truth": True,
            "dedupe_key": f"workflow:{subtype}:{title}",
        },
        "content_refs": ([{"ref_type": "inline_text", "ref": "", "snippet": content, "checksum": ""}] if content.strip() else []),
        "quality": {"confidence": 1.0, "verification_state": "asserted", "evidence_refs": []},
        "relevancy": {},
        "lifecycle": {"status": "active", "effective_from": None, "effective_to": None, "staleness_ttl_seconds": 0},
        "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
        "kind_payload": {"subtype": subtype, "content": content},
        "schema_version": "v1",
    }


def _execute_document_draft_node(*, auth: Any, org_id: str, node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config", {}) if isinstance(node.get("config"), dict) else {}
    title = str(config.get("title", node.get("label", "Generated Draft"))).strip() or "Generated Draft"
    prompt = str(config.get("prompt", "")).strip() or title
    profile_id = str(config.get("profile_id", "")).strip() or None
    provider_id, model_id = resolve_provider_preference(
        profile_id=profile_id,
        capability="document_drafting",
        provider_id=str(config.get("provider_id", "")).strip() or None,
        model_id=str(config.get("model_id", "")).strip() or None,
    )
    provider_id = provider_id or "anthropic"
    fallback_content = f"# {title}\n\n## Request\n{prompt}\n"
    provider_used = provider_id
    model_used = model_id
    try:
        result = model_gateway.generate_text_sync(
            ModelRequest(
                system_prompt="You are generating a structured markdown workflow document. Return clear headings and concise sections.",
                conversation_messages=[{"role": "user", "content": prompt}],
                model_profile="balanced",
                provider_id=provider_id,
                model_id=model_id,
                tenant_id=auth.tenant_id,
                org_id=org_id,
            )
        )
        content = result.content
        provider_used = result.provider
        model_used = result.model
    except Exception:
        content = fallback_content
        provider_used = provider_id or "deterministic"
        model_used = model_id or "document-draft-fallback-v1"
    emit_artifact = bool(config.get("emit_artifact", True))
    artifact = None
    if emit_artifact:
        artifact = _build_workflow_artifact(title=title, subtype="workflow_document_draft", content=content, created_by_user_id=auth.user_id)
        knowledge_contract_store.upsert_entities(tenant_id=auth.tenant_id, org_id=org_id, items=[artifact])
    return {
        "node_id": node.get("node_id"),
        "kind": node.get("kind"),
        "status": "completed",
        "content": content,
        "provider_id": provider_used,
        "model_id": model_used,
        "artifact_entity_id": artifact.get("entity_id") if isinstance(artifact, dict) else None,
    }


def _execute_task_create_node(*, auth: Any, org_id: str, node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config", {}) if isinstance(node.get("config"), dict) else {}
    prompt = str(config.get("prompt", node.get("label", "New Task"))).strip()
    title = str(config.get("title", prompt.splitlines()[0][:120] if prompt else node.get("label", "New Task"))).strip() or "New Task"
    task = collaboration_store.create_task(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        owner_user_id=auth.user_id,
        title=title,
        description=str(config.get("description", prompt)).strip(),
        visibility=str(config.get("visibility", "org_public")),
        status=str(config.get("status", "todo")),
        team_id=str(config.get("team_id", "")).strip() or None,
        tags=[str(item) for item in config.get("tags", []) if str(item).strip()] if isinstance(config.get("tags"), list) else [],
        metadata={"created_from": "workflow_node", **(config.get("metadata", {}) if isinstance(config.get("metadata"), dict) else {})},
        related_node_ids=[],
        channel_id=str(config.get("channel_id", "")).strip() or None,
    )
    return {
        "node_id": node.get("node_id"),
        "kind": node.get("kind"),
        "status": "completed",
        "task_id": task["task_id"],
        "title": task["title"],
    }


def _run_workflow_nodes(*, auth: Any, workflow: dict[str, Any], artifact: dict[str, Any], review_context: dict[str, Any], start_node_id: str) -> dict[str, Any]:
    org_id = workflow["org_id"]
    nodes = workflow.get("nodes", []) if isinstance(workflow.get("nodes", []), list) else []
    edges = workflow.get("edges", []) if isinstance(workflow.get("edges", []), list) else []
    node_map = _node_map(nodes)
    adjacency = _edge_map(edges)
    trace: list[dict[str, Any]] = []
    current_node_id = start_node_id
    max_steps = max(1, len(nodes) + len(edges) + 5)
    steps = 0
    blocked = False
    review_required = False
    matched_rules: list[dict[str, Any]] = []
    review_item_context = dict(review_context)
    while current_node_id and steps < max_steps:
        node = node_map.get(current_node_id)
        if node is None:
            blocked = True
            break
        kind = str(node.get("kind", "")).strip()
        if kind == "review_gate":
            review_required = True
            review_item_context = {**review_context, "current_node_id": current_node_id}
            trace.append({"node_id": current_node_id, "kind": kind, "status": "paused_review"})
            break
        if kind == "document_draft":
            result = _execute_document_draft_node(auth=auth, org_id=org_id, node=node)
            trace.append(result)
        elif kind == "task_create":
            result = _execute_task_create_node(auth=auth, org_id=org_id, node=node)
            trace.append(result)
        else:
            trace.append({"node_id": current_node_id, "kind": kind, "status": "skipped_unsupported"})
        steps += 1
        current_node_id = _next_node_from_edges(adjacency, current_node_id)
    if steps >= max_steps and current_node_id:
        blocked = True
    return {
        "artifact": artifact,
        "trace": trace,
        "blocked": blocked,
        "review_required": review_required,
        "matched_rules": matched_rules,
        "current_node_id": current_node_id,
        "review_context": review_item_context,
    }


@router.post("/workflows")
def create_workflow(request: Request, payload: WorkflowCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    _enforce_org_scope(auth.org_id, payload.org_id, is_global_admin=auth.is_global_admin)
    _validate_workflow_graph(nodes=payload.nodes, edges=payload.edges, logic_rules=payload.logic_rules)
    created = workflow_store.create_definition(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        description=payload.description,
        trigger=payload.trigger,
        nodes=payload.nodes,
        edges=payload.edges,
        logic_rules=payload.logic_rules,
        policy=payload.policy,
        metadata=payload.metadata,
        created_by_user_id=auth.user_id,
        spec_version=payload.spec_version,
    )
    return ok_response(request, data=created)


@router.get("/workflows")
def list_workflows(request: Request, org_id: str = Query(min_length=1), limit: int = 100) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth.org_id, org_id, is_global_admin=auth.is_global_admin)
    items = workflow_store.list_definitions(tenant_id=auth.tenant_id, org_id=org_id, limit=max(1, min(limit, 200)))
    return ok_response(request, data={"items": items})






@router.get("/workflows/{workflow_id}")
def get_workflow(request: Request, workflow_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = workflow_store.get_definition(tenant_id=auth.tenant_id, workflow_id=workflow_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, item["org_id"], is_global_admin=auth.is_global_admin)
    return ok_response(request, data=item)


@router.patch("/workflows/{workflow_id}")
def patch_workflow(request: Request, workflow_id: str, payload: WorkflowPatchPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    existing = workflow_store.get_definition(tenant_id=auth.tenant_id, workflow_id=workflow_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, existing["org_id"], is_global_admin=auth.is_global_admin)
    next_nodes = payload.nodes if payload.nodes is not None else existing.get("nodes", [])
    next_edges = payload.edges if payload.edges is not None else existing.get("edges", [])
    next_rules = payload.logic_rules if payload.logic_rules is not None else existing.get("logic_rules", [])
    _validate_workflow_graph(nodes=next_nodes, edges=next_edges, logic_rules=next_rules)
    updated = workflow_store.update_definition(
        tenant_id=auth.tenant_id,
        workflow_id=workflow_id,
        name=payload.name,
        description=payload.description,
        trigger=payload.trigger,
        nodes=payload.nodes,
        edges=payload.edges,
        logic_rules=payload.logic_rules,
        policy=payload.policy,
        metadata=payload.metadata,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    return ok_response(request, data=updated)


@router.post("/workflows/{workflow_id}/runs")
def start_workflow_run(request: Request, workflow_id: str, payload: WorkflowRunStartPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = workflow_store.get_definition(tenant_id=auth.tenant_id, workflow_id=workflow_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, item["org_id"], is_global_admin=auth.is_global_admin)
    nodes = item.get("nodes", []) if isinstance(item.get("nodes", []), list) else []
    edges = item.get("edges", []) if isinstance(item.get("edges", []), list) else []
    start_node_id = _resolve_start_node_id(nodes=nodes, edges=edges, requested_start_node_id=payload.start_node_id)
    evaluation = evaluate_artifact_rules(
        artifact=dict(payload.artifact),
        rules=item.get("logic_rules", []) if isinstance(item.get("logic_rules", []), list) else [],
    )
    execution = _run_workflow_nodes(
        auth=auth,
        workflow=item,
        artifact=evaluation["artifact"],
        review_context=payload.review_context,
        start_node_id=start_node_id,
    )
    review_required = bool(evaluation["review_required"] or execution["review_required"])
    blocked = bool(evaluation["blocked"] or execution["blocked"])
    matched_rules = [*evaluation["matched_rules"], *execution["matched_rules"]]
    run_status = "paused_review" if review_required else ("failed" if blocked else "completed")
    run = workflow_store.create_run(
        tenant_id=auth.tenant_id,
        org_id=item["org_id"],
        workflow_id=workflow_id,
        status=run_status,
        artifact=execution["artifact"],
        review_context={**execution["review_context"], "current_node_id": execution["current_node_id"], "execution_trace": execution["trace"]},
        matched_rules=matched_rules,
        created_by_user_id=auth.user_id,
    )
    review_item = None
    if review_required:
        review_item = workflow_store.create_review_item(
            tenant_id=auth.tenant_id,
            org_id=item["org_id"],
            workflow_id=workflow_id,
            run_id=run["run_id"],
            node_id=str(execution["review_context"].get("node_id", execution["current_node_id"] or start_node_id)).strip() or str(execution["current_node_id"] or start_node_id),
            title=str(payload.review_context.get("title", item.get("name", "Workflow Review"))).strip() or "Workflow Review",
            summary=str(payload.review_context.get("summary", "Workflow execution requires review.")).strip() or "Workflow execution requires review.",
            reason_code=(execution["artifact"].get("quality", {}) if isinstance(execution["artifact"].get("quality", {}), dict) else {}).get("review_reason", "workflow_review_required"),
            requested_by_user_id=auth.user_id,
            context={
                **execution["review_context"],
                "matched_rules": matched_rules,
                "artifact": execution["artifact"],
                "current_node_id": execution["current_node_id"],
                "execution_trace": execution["trace"],
            },
        )
    return ok_response(
        request,
        data={
            "workflow_id": workflow_id,
            "run": run,
            "current_node_id": execution["current_node_id"],
            "artifact": execution["artifact"],
            "blocked": blocked,
            "review_required": review_required,
            "matched_rules": matched_rules,
            "review_context": execution["review_context"],
            "execution_trace": execution["trace"],
            "review_item": review_item,
        },
    )


@router.post("/workflows/{workflow_id}/dry-run")
def dry_run_workflow(request: Request, workflow_id: str, payload: WorkflowDryRunPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = workflow_store.get_definition(tenant_id=auth.tenant_id, workflow_id=workflow_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, item["org_id"], is_global_admin=auth.is_global_admin)
    evaluation = evaluate_artifact_rules(
        artifact=dict(payload.artifact),
        rules=item.get("logic_rules", []) if isinstance(item.get("logic_rules", []), list) else [],
    )
    run_status = "paused_review" if evaluation["review_required"] else ("failed" if evaluation["blocked"] else "completed")
    run = workflow_store.create_run(
        tenant_id=auth.tenant_id,
        org_id=item["org_id"],
        workflow_id=workflow_id,
        status=run_status,
        artifact=evaluation["artifact"],
        review_context=payload.review_context,
        matched_rules=evaluation["matched_rules"],
        created_by_user_id=auth.user_id,
    )
    review_item = None
    if evaluation["review_required"]:
        review_item = workflow_store.create_review_item(
            tenant_id=auth.tenant_id,
            org_id=item["org_id"],
            workflow_id=workflow_id,
            run_id=run["run_id"],
            node_id=str(payload.review_context.get("node_id", "")).strip(),
            title=str(payload.review_context.get("title", item.get("name", "Workflow Review"))).strip() or "Workflow Review",
            summary=str(payload.review_context.get("summary", "Workflow execution requires review.")).strip() or "Workflow execution requires review.",
            reason_code=(evaluation["artifact"].get("quality", {}) if isinstance(evaluation["artifact"].get("quality", {}), dict) else {}).get("review_reason", "workflow_review_required"),
            requested_by_user_id=auth.user_id,
            context={
                **payload.review_context,
                "matched_rules": evaluation["matched_rules"],
                "artifact": evaluation["artifact"],
            },
        )
    return ok_response(
        request,
        data={
            "workflow_id": workflow_id,
            "run": run,
            "artifact": evaluation["artifact"],
            "blocked": evaluation["blocked"],
            "review_required": evaluation["review_required"],
            "matched_rules": evaluation["matched_rules"],
            "review_context": payload.review_context,
            "review_item": review_item,
        },
    )


@router.get("/workflows/{workflow_id}/runs")
def list_workflow_runs(request: Request, workflow_id: str, limit: int = 100) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    item = workflow_store.get_definition(tenant_id=auth.tenant_id, workflow_id=workflow_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, item["org_id"], is_global_admin=auth.is_global_admin)
    runs = workflow_store.list_runs(tenant_id=auth.tenant_id, workflow_id=workflow_id, limit=max(1, min(limit, 200)))
    return ok_response(request, data={"items": runs})


@router.get("/workflow-runs/{run_id}")
def get_workflow_run(request: Request, run_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    run = workflow_store.get_run(tenant_id=auth.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow run not found.", "details": {"reason_code": "STUDIO_WORKFLOW_RUN_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, run["org_id"], is_global_admin=auth.is_global_admin)
    return ok_response(request, data=run)


@router.post("/workflow-runs/{run_id}/resume")
def resume_workflow_run(request: Request, run_id: str, payload: WorkflowRunResumePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    run = workflow_store.get_run(tenant_id=auth.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow run not found.", "details": {"reason_code": "STUDIO_WORKFLOW_RUN_NOT_FOUND"}},
        )
    _enforce_org_scope(auth.org_id, run["org_id"], is_global_admin=auth.is_global_admin)
    workflow = workflow_store.get_definition(tenant_id=auth.tenant_id, workflow_id=run["workflow_id"])
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow not found.", "details": {"reason_code": "STUDIO_WORKFLOW_NOT_FOUND"}},
        )
    current_context = run.get("review_context", {}) if isinstance(run.get("review_context", {}), dict) else {}
    current_node_id = str(current_context.get("current_node_id", "")).strip()
    if not current_node_id:
        raise HTTPException(
            status_code=422,
            detail={"message": "Workflow run cannot be resumed without a current node.", "details": {"reason_code": "STUDIO_WORKFLOW_RUN_RESUME_INVALID"}},
        )
    next_edges = workflow.get("edges", []) if isinstance(workflow.get("edges", []), list) else []
    start_node_id = _next_node_from_edges(_edge_map(next_edges), current_node_id)
    if not start_node_id:
        updated = workflow_store.update_run_status(tenant_id=auth.tenant_id, run_id=run_id, status="completed")
        return ok_response(request, data={"run": updated, "execution_trace": current_context.get("execution_trace", [])})
    artifact = payload.artifact if isinstance(payload.artifact, dict) and payload.artifact else (run.get("artifact", {}) if isinstance(run.get("artifact", {}), dict) else {})
    execution = _run_workflow_nodes(
        auth=auth,
        workflow=workflow,
        artifact=artifact,
        review_context={**current_context, **payload.review_context},
        start_node_id=start_node_id,
    )
    review_required = execution["review_required"]
    blocked = execution["blocked"]
    new_status = "paused_review" if review_required else ("failed" if blocked else "completed")
    existing_trace = current_context.get("execution_trace", []) if isinstance(current_context.get("execution_trace", []), list) else []
    existing_matched_rules = run.get("matched_rules", []) if isinstance(run.get("matched_rules", []), list) else []
    updated = workflow_store.update_run(
        tenant_id=auth.tenant_id,
        run_id=run_id,
        status=new_status,
        artifact=execution["artifact"],
        review_context={**execution["review_context"], "current_node_id": execution["current_node_id"], "execution_trace": [*existing_trace, *execution["trace"]]},
        matched_rules=[*existing_matched_rules, *execution["matched_rules"]],
    )
    review_item = None
    if review_required:
        review_item = workflow_store.create_review_item(
            tenant_id=auth.tenant_id,
            org_id=workflow["org_id"],
            workflow_id=workflow["workflow_id"],
            run_id=run_id,
            node_id=str(execution["review_context"].get("node_id", execution["current_node_id"] or start_node_id)).strip() or str(execution["current_node_id"] or start_node_id),
            title=str(execution["review_context"].get("title", workflow.get("name", "Workflow Review"))).strip() or "Workflow Review",
            summary=str(execution["review_context"].get("summary", "Workflow execution requires review.")).strip() or "Workflow execution requires review.",
            reason_code=(execution["artifact"].get("quality", {}) if isinstance(execution["artifact"].get("quality", {}), dict) else {}).get("review_reason", "workflow_review_required"),
            requested_by_user_id=auth.user_id,
            context={**execution["review_context"], "matched_rules": execution["matched_rules"], "artifact": execution["artifact"], "current_node_id": execution["current_node_id"], "execution_trace": execution["trace"]},
        )
    return ok_response(request, data={"run": updated, "execution_trace": updated["review_context"]["execution_trace"], "review_item": review_item})


@router.get("/workflow-reviews")
def list_workflow_reviews(request: Request, org_id: str = Query(min_length=1), status: str | None = None, limit: int = 100) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    _enforce_org_scope(auth.org_id, org_id, is_global_admin=auth.is_global_admin)
    items = workflow_store.list_review_items(tenant_id=auth.tenant_id, org_id=org_id, status=status, limit=max(1, min(limit, 200)))
    return ok_response(request, data={"items": items})


@router.post("/workflow-reviews/{review_id}/decision")
def decide_workflow_review(request: Request, review_id: str, payload: WorkflowReviewDecisionPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    review = workflow_store.resolve_review_item(
        tenant_id=auth.tenant_id,
        review_id=review_id,
        decision=("approved" if payload.decision == "approve" else payload.decision),
        resolved_by_user_id=auth.user_id,
    )
    if review is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workflow review not found.", "details": {"reason_code": "STUDIO_WORKFLOW_REVIEW_NOT_FOUND"}},
        )
    run_id = str(review.get("run_id", "")).strip()
    if run_id:
        new_status = "completed" if payload.decision == "approve" else ("failed" if payload.decision == "reject" else "paused_waiting")
        workflow_store.update_run_status(tenant_id=auth.tenant_id, run_id=run_id, status=new_status)
    return ok_response(request, data=review)


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
