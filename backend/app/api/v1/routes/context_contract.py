from __future__ import annotations

from typing import Any
from uuid import uuid4
from datetime import UTC, datetime, timedelta
import json

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select

from app.core.auth_context import require_authentication, require_roles
from app.core.audit_store import audit_store
from app.core.collaboration_store import collaboration_store
from app.core.daily_summary_store import daily_summary_store
from app.core.db import SessionLocal
from app.core.db_models import (
    AuditEventModel,
    KnowledgeEntityModel,
    StudioMeetingModel,
    StudioMeetingParticipantModel,
    StudioOrganizationMembershipModel,
    StudioTaskAssignmentModel,
    StudioTaskModel,
    StudioTeamMembershipModel,
)
from app.core.document_extraction import extract_document_text
from app.core.document_storage import document_storage
from app.core.knowledge_contract_store import knowledge_contract_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.persona_prompt import compile_persona_system_prompt_resolved
from app.core.response import ok_response
from app.core.suite_store import suite_store

router = APIRouter(tags=["knowledge-contract"])

SELECTION_REASON_CODES = {
    "semantic_match",
    "policy_priority",
    "graph_proximity",
    "owner_authority",
    "freshness_boost",
}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class KnowledgeEntitiesUpsertPayload(BaseModel):
    org_id: str = Field(min_length=1)
    items: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeRelationshipsUpsertPayload(BaseModel):
    org_id: str = Field(min_length=1)
    items: list[dict[str, Any]] = Field(default_factory=list)


class GraphIngestDeltaPayload(BaseModel):
    source_system: str = Field(min_length=1)
    source_scope: dict[str, Any] = Field(default_factory=dict)
    entities_upsert: list[dict[str, Any]] = Field(default_factory=list)
    relationships_upsert: list[dict[str, Any]] = Field(default_factory=list)


class ContextResolvePayload(BaseModel):
    anchor: dict[str, Any] = Field(default_factory=dict)
    lens: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class PersonaContextQueryPayload(BaseModel):
    persona_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    anchor: dict[str, Any] = Field(default_factory=dict)
    lens: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class PolicyDecisionPayload(BaseModel):
    subject: dict[str, Any] = Field(default_factory=dict)
    resource: dict[str, Any] = Field(default_factory=dict)
    action: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class EventIngestPayload(BaseModel):
    app_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    resource_type: str = Field(default="event")
    resource_id: str = Field(default="")
    workspace_id: str = Field(default="")
    correlation_id: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


def _extract_assigned_tools_from_persona(persona: dict[str, Any]) -> list[str]:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    assigned = data.get("assigned_tools", []) if isinstance(data.get("assigned_tools"), list) else []
    cleaned = [str(item).strip() for item in assigned if str(item).strip()]
    if cleaned:
        return cleaned
    policies = data.get("operational_policies", {}) if isinstance(data.get("operational_policies"), dict) else {}
    policy_tools = policies.get("tool_policies", []) if isinstance(policies.get("tool_policies"), list) else []
    parsed: list[str] = []
    for item in policy_tools:
        value = str(item).strip()
        if not value:
            continue
        if value.startswith("enabled_tool:"):
            value = value.split(":", 1)[1].strip()
        parsed.append(value)
    return [item for item in parsed if item]


def _persona_capability_payload(persona: dict[str, Any]) -> dict[str, Any]:
    provider_id, model_id = _persona_runtime_settings(persona)
    return {
        "persona_id": persona.get("persona_id"),
        "org_id": persona.get("org_id"),
        "name": persona.get("name"),
        "slug": persona.get("slug"),
        "role": persona.get("role"),
        "scope": persona.get("scope"),
        "enabled": bool(persona.get("enabled", True)),
        "approval_status": str(persona.get("approval_status", "draft")),
        "model_profile": str(persona.get("model_profile", "reasoning-optimized")),
        "runtime": {
            "provider_id": provider_id,
            "model_id": model_id,
        },
        "access": {
            "visibility": _persona_access_level(persona),
        },
        "tools": _extract_assigned_tools_from_persona(persona),
    }


def _validate_selection_reason_codes(result: dict[str, Any]) -> None:
    sources = result.get("sources", []) if isinstance(result.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        code = str(source.get("selection_reason_code", "")).strip()
        if code not in SELECTION_REASON_CODES:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Resolver returned unsupported selection reason code.",
                    "details": {
                        "reason_code": "KNOWLEDGE_SELECTION_REASON_CODE_INVALID",
                        "value": code,
                    },
                },
            )


def _build_context_quality(result: dict[str, Any], *, max_nodes: int) -> dict[str, Any]:
    sources = result.get("sources", []) if isinstance(result.get("sources"), list) else []
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    selected_nodes = int(summary.get("selected_nodes", len(sources)) or 0)
    scores: list[float] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        score = source.get("score")
        if isinstance(score, int | float):
            scores.append(float(score))
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    coverage_ratio = round(min(1.0, selected_nodes / max(1, max_nodes)), 4)

    quality = "low"
    if avg_score >= 0.75 and selected_nodes >= 3:
        quality = "high"
    elif avg_score >= 0.5 and selected_nodes >= 2:
        quality = "medium"

    follow_up_recommended = quality == "low"
    reasons: list[str] = []
    if selected_nodes == 0:
        reasons.append("no_sources")
    if avg_score < 0.5:
        reasons.append("low_relevance")
    if coverage_ratio < 0.2:
        reasons.append("narrow_coverage")

    return {
        "quality": quality,
        "selected_nodes": selected_nodes,
        "average_score": avg_score,
        "coverage_ratio": coverage_ratio,
        "follow_up_recommended": follow_up_recommended,
        "follow_up_reasons": reasons,
    }


def _safe_json_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _safe_json_list(raw: str) -> list[Any]:
    try:
        value = json.loads(raw)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _build_daily_summary_data(
    *,
    tenant_id: str,
    org_id: str,
    user_id: str,
    day_start: datetime,
    day_end: datetime,
) -> tuple[list[str], dict[str, list[str]], dict[str, int]]:
    with SessionLocal() as db:
        task_rows = db.scalars(
            select(StudioTaskModel).where(
                StudioTaskModel.tenant_id == tenant_id,
                StudioTaskModel.org_id == org_id,
                or_(
                    and_(StudioTaskModel.created_at >= day_start, StudioTaskModel.created_at < day_end),
                    and_(StudioTaskModel.updated_at >= day_start, StudioTaskModel.updated_at < day_end),
                ),
            )
        ).all()

        assigned_task_ids = db.scalars(
            select(StudioTaskAssignmentModel.task_id).where(
                StudioTaskAssignmentModel.tenant_id == tenant_id,
                StudioTaskAssignmentModel.assignee_user_id == user_id,
            )
        ).all()
        assigned_set = {str(item) for item in assigned_task_ids}

        meeting_participant_ids = db.scalars(
            select(StudioMeetingParticipantModel.meeting_id).where(
                StudioMeetingParticipantModel.tenant_id == tenant_id,
                StudioMeetingParticipantModel.user_id == user_id,
            )
        ).all()
        meeting_participant_set = {str(item) for item in meeting_participant_ids}
        meeting_identity_filter = (
            or_(
                StudioMeetingModel.created_by_user_id == user_id,
                StudioMeetingModel.meeting_id.in_(list(meeting_participant_set)),
            )
            if meeting_participant_set
            else StudioMeetingModel.created_by_user_id == user_id
        )
        meeting_rows = db.scalars(
            select(StudioMeetingModel).where(
                StudioMeetingModel.tenant_id == tenant_id,
                StudioMeetingModel.org_id == org_id,
                meeting_identity_filter,
                or_(
                    and_(StudioMeetingModel.created_at >= day_start, StudioMeetingModel.created_at < day_end),
                    and_(StudioMeetingModel.updated_at >= day_start, StudioMeetingModel.updated_at < day_end),
                    and_(StudioMeetingModel.scheduled_start_at >= day_start, StudioMeetingModel.scheduled_start_at < day_end),
                ),
            )
        ).all()

        audit_rows = db.scalars(
            select(AuditEventModel).where(
                AuditEventModel.tenant_id == tenant_id,
                AuditEventModel.actor_id == user_id,
                AuditEventModel.created_at >= day_start,
                AuditEventModel.created_at < day_end,
            )
        ).all()

        uploaded_rows = db.scalars(
            select(KnowledgeEntityModel).where(
                KnowledgeEntityModel.tenant_id == tenant_id,
                KnowledgeEntityModel.org_id == org_id,
                KnowledgeEntityModel.kind == "document",
                KnowledgeEntityModel.created_at >= day_start,
                KnowledgeEntityModel.created_at < day_end,
            )
        ).all()

    task_bullets: list[str] = []
    completed = 0
    updated = 0
    for row in task_rows:
        is_assigned = row.task_id in assigned_set
        if row.owner_user_id != user_id and not is_assigned:
            continue
        if row.status == "done":
            completed += 1
        updated_at = _as_utc(row.updated_at)
        if updated_at and updated_at >= day_start and updated_at < day_end:
            updated += 1
        task_bullets.append(f"{row.title} ({row.status})")

    meeting_bullets = [f"{row.title} ({row.status})" for row in meeting_rows]

    upload_bullets: list[str] = []
    for row in uploaded_rows:
        owners = _safe_json_list(row.owners_json)
        owner_ids = {str(item.get("owner_id", "")) for item in owners if isinstance(item, dict)}
        if user_id not in owner_ids:
            continue
        upload_bullets.append(row.title)

    audit_bullets: list[str] = []
    for row in audit_rows:
        metadata = _safe_json_dict(row.metadata_json)
        resource = f"{row.resource_type}:{row.resource_id}" if row.resource_type else row.action
        if metadata:
            audit_bullets.append(f"{row.action} on {resource}")
        else:
            audit_bullets.append(f"{row.action}")

    highlights: list[str] = []
    if completed > 0:
        highlights.append(f"Completed {completed} task(s).")
    if len(meeting_bullets) > 0:
        highlights.append(f"Participated in {len(meeting_bullets)} meeting event(s).")
    if len(upload_bullets) > 0:
        highlights.append(f"Uploaded {len(upload_bullets)} document(s) to knowledge base.")
    if updated > completed and updated > 0:
        highlights.append(f"Updated {updated} task(s) in progress.")
    if not highlights:
        highlights.append("No major tracked activity found for this day.")

    sections = {
        "tasks": task_bullets[:20],
        "meetings": meeting_bullets[:20],
        "uploads": upload_bullets[:20],
        "activity": audit_bullets[:20],
    }
    summary = {
        "tasks_total": len(task_bullets),
        "tasks_completed": completed,
        "meetings_total": len(meeting_bullets),
        "uploads_total": len(upload_bullets),
        "audit_events_total": len(audit_bullets),
    }
    return highlights, sections, summary


def _load_user_identity_context(*, tenant_id: str, org_id: str, user_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        memberships = db.scalars(
            select(StudioOrganizationMembershipModel).where(
                StudioOrganizationMembershipModel.tenant_id == tenant_id,
                StudioOrganizationMembershipModel.org_id == org_id,
                StudioOrganizationMembershipModel.user_id == user_id,
                StudioOrganizationMembershipModel.status == "active",
            )
        ).all()
        team_memberships = db.scalars(
            select(StudioTeamMembershipModel).where(
                StudioTeamMembershipModel.tenant_id == tenant_id,
                StudioTeamMembershipModel.user_id == user_id,
                StudioTeamMembershipModel.status == "active",
            )
        ).all()
    roles = sorted({str(item.role) for item in memberships})
    team_ids = sorted({str(item.team_id) for item in team_memberships})
    role_ids = [f"org:{role}" for role in roles]
    grants = suite_store.list_app_access_grants(tenant_id=tenant_id, org_id=org_id, user_id=user_id)
    app_access: dict[str, dict[str, Any]] = {}
    for grant in grants:
        if str(grant.get("status", "")).strip().lower() != "active":
            continue
        app_id = str(grant.get("app_id", "")).strip()
        if not app_id:
            continue
        app_access[app_id] = {
            "role": str(grant.get("role", "member")),
            "capabilities": grant.get("feature_flags", []) if isinstance(grant.get("feature_flags"), list) else [],
        }
    return {
        "org_id": org_id,
        "team_ids": team_ids,
        "role_ids": role_ids,
        "app_access": app_access,
    }


def _evaluate_policy_decision(*, identity: dict[str, Any], action: str, context: dict[str, Any]) -> dict[str, Any]:
    app_access = identity.get("app_access", {}) if isinstance(identity.get("app_access"), dict) else {}
    app_id = str(context.get("app_id", "")).strip()
    if not app_id:
        return {"allow": False, "reason_code": "POLICY_APP_ID_REQUIRED", "decision_basis": "input_validation"}
    grant = app_access.get(app_id)
    if grant is None:
        return {"allow": False, "reason_code": "POLICY_APP_ACCESS_DENIED", "decision_basis": "app_grant_missing"}
    capabilities = {str(item).strip() for item in (grant.get("capabilities", []) or []) if str(item).strip()}
    if f"{app_id}:access" not in capabilities and "*" not in capabilities:
        return {
            "allow": False,
            "reason_code": "POLICY_APP_BASE_ACCESS_REQUIRED",
            "decision_basis": "capability_missing",
        }
    if action not in capabilities and "*" not in capabilities:
        return {
            "allow": False,
            "reason_code": "POLICY_CAPABILITY_DENIED",
            "decision_basis": "capability_missing",
        }
    return {"allow": True, "reason_code": "POLICY_ALLOW", "decision_basis": "explicit_capability_allow"}


def _parse_json_form(raw: str | None, *, default: Any, field_name: str) -> Any:
    if raw is None or raw.strip() == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid JSON for {field_name}.",
                "details": {"reason_code": "KNOWLEDGE_UPLOAD_JSON_INVALID", "field": field_name},
            },
        ) from exc


def _require_entity_fields(item: dict[str, Any]) -> None:
    required = {
        "entity_id",
        "kind",
        "title",
        "source",
        "visibility",
        "timestamps",
        "kind_schema_version",
        "schema_version",
    }
    missing = sorted(field for field in required if field not in item)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge entity payload is missing required fields.",
                "details": {"reason_code": "KNOWLEDGE_ENTITY_FIELDS_MISSING", "fields": missing},
            },
        )
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    if "source_of_truth" not in source:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge entity source_of_truth is required.",
                "details": {"reason_code": "KNOWLEDGE_ENTITY_SOURCE_OF_TRUTH_REQUIRED"},
            },
        )
    timestamps = item.get("timestamps") if isinstance(item.get("timestamps"), dict) else {}
    if "observed_at" not in timestamps:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge entity observed_at is required.",
                "details": {"reason_code": "KNOWLEDGE_ENTITY_OBSERVED_AT_REQUIRED"},
            },
        )


def _require_relationship_fields(item: dict[str, Any]) -> None:
    required = {
        "relationship_id",
        "from_entity_id",
        "to_entity_id",
        "relationship_type",
        "directionality",
        "source",
        "visibility",
        "timestamps",
        "schema_version",
    }
    missing = sorted(field for field in required if field not in item)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge relationship payload is missing required fields.",
                "details": {"reason_code": "KNOWLEDGE_RELATIONSHIP_FIELDS_MISSING", "fields": missing},
            },
        )
    timestamps = item.get("timestamps") if isinstance(item.get("timestamps"), dict) else {}
    if "observed_at" not in timestamps:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge relationship observed_at is required.",
                "details": {"reason_code": "KNOWLEDGE_RELATIONSHIP_OBSERVED_AT_REQUIRED"},
            },
        )


def _persona_access_level(persona: dict[str, Any]) -> str:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    access = data.get("access_policy", {}) if isinstance(data.get("access_policy"), dict) else {}
    level = str(access.get("visibility", "organization")).strip().lower()
    return level or "organization"


def _can_access_persona(*, auth: Any, persona: dict[str, Any]) -> bool:
    level = _persona_access_level(persona)
    if level in {"admin_only", "restricted_admin"}:
        return bool(auth.is_global_admin or any(role in {"owner", "admin"} for role in auth.roles))
    return True


def _persona_runtime_settings(persona: dict[str, Any]) -> tuple[str | None, str | None]:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    provider_id = str(runtime.get("provider_id", "")).strip().lower() or None
    model_id = str(runtime.get("model_id", "")).strip() or None
    return provider_id, model_id


def _build_context_snippet(result: dict[str, Any], *, max_items: int = 8) -> str:
    sources = result.get("sources", []) if isinstance(result.get("sources"), list) else []
    lines: list[str] = []
    for index, source in enumerate(sources[:max_items], start=1):
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "Untitled")).strip() or "Untitled"
        kind = str(source.get("kind", "")).strip() or "entity"
        score = source.get("score", 0)
        lines.append(f"{index}. [{kind}] {title} (score={score})")
    if not lines:
        return "No federated context candidates were found."
    return "\n".join(lines)


CHANNEL_PROFILES: list[dict[str, Any]] = [
    {
        "channel_profile_id": "development-default",
        "label": "Development",
        "description": "Code-aware context retrieval for implementation and debugging.",
        "defaults": {
            "include_node_kinds": ["project", "task", "file", "symbol", "document", "tool", "policy"],
            "include_relationship_types": [
                "contains",
                "depends_on",
                "imports",
                "implements",
                "uses_tool",
                "governed_by",
            ],
            "max_nodes": 40,
            "max_edges": 80,
            "max_snippets": 20,
            "max_tokens": 8000,
        },
    },
    {
        "channel_profile_id": "architecture-default",
        "label": "Architecture",
        "description": "Broader dependency and policy context for cross-repo planning.",
        "defaults": {
            "include_node_kinds": ["project", "service", "repo", "document", "policy", "workflow"],
            "include_relationship_types": ["contains", "depends_on", "exposes_contract", "consumed_by", "governed_by"],
            "max_nodes": 50,
            "max_edges": 100,
            "max_snippets": 24,
            "max_tokens": 10000,
        },
    },
    {
        "channel_profile_id": "operations-default",
        "label": "Operations",
        "description": "Operational runbooks, policy constraints, and ownership metadata.",
        "defaults": {
            "include_node_kinds": ["workflow", "policy", "service", "team", "user", "document"],
            "include_relationship_types": ["governed_by", "requires_permission", "escalates_to", "related_to"],
            "max_nodes": 35,
            "max_edges": 70,
            "max_snippets": 18,
            "max_tokens": 7000,
        },
    },
]


@router.post("/knowledge/entities/upsert")
def upsert_entities(request: Request, payload: KnowledgeEntitiesUpsertPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    for item in payload.items:
        _require_entity_fields(item)
    items = knowledge_contract_store.upsert_entities(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        items=payload.items,
    )
    return ok_response(request, data={"items": items})


@router.post("/knowledge/relationships/upsert")
def upsert_relationships(request: Request, payload: KnowledgeRelationshipsUpsertPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    for item in payload.items:
        _require_relationship_fields(item)
    items = knowledge_contract_store.upsert_relationships(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        items=payload.items,
    )
    return ok_response(request, data={"items": items})


@router.post("/graph/ingest-delta")
def ingest_delta(request: Request, payload: GraphIngestDeltaPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    scope_org = str(payload.source_scope.get("org_id") or auth.org_id or "")
    if not scope_org:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "source_scope.org_id is required.",
                "details": {"reason_code": "KNOWLEDGE_INGEST_SCOPE_ORG_REQUIRED"},
            },
        )
    for item in payload.entities_upsert:
        _require_entity_fields(item)
    for item in payload.relationships_upsert:
        _require_relationship_fields(item)
    entities = knowledge_contract_store.upsert_entities(
        tenant_id=auth.tenant_id,
        org_id=scope_org,
        items=payload.entities_upsert,
    )
    relationships = knowledge_contract_store.upsert_relationships(
        tenant_id=auth.tenant_id,
        org_id=scope_org,
        items=payload.relationships_upsert,
    )
    return ok_response(
        request,
        data={
            "source_system": payload.source_system,
            "entities_upserted": len(entities),
            "relationships_upserted": len(relationships),
        },
    )


@router.post("/context/resolve")
def resolve_context(request: Request, payload: ContextResolvePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    anchor = payload.anchor if isinstance(payload.anchor, dict) else {}
    lens = payload.lens if isinstance(payload.lens, dict) else {}
    budget = payload.budget if isinstance(payload.budget, dict) else {}
    options = payload.options if isinstance(payload.options, dict) else {}
    result = knowledge_contract_store.resolve(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        anchor_entity_id=anchor.get("entity_id"),
        anchor_text=str(anchor.get("text") or ""),
        include_node_kinds=set(lens.get("include_node_kinds", []))
        if isinstance(lens.get("include_node_kinds"), list)
        else set(),
        include_relationship_types=set(lens.get("include_relationship_types", []))
        if isinstance(lens.get("include_relationship_types"), list)
        else set(),
        max_nodes=int(budget.get("max_nodes", 40)),
        max_edges=int(budget.get("max_edges", 80)),
        max_snippets=int(budget.get("max_snippets", 20)),
        max_tokens=int(budget.get("max_tokens", 8000)),
        debug=bool(options.get("include_exclusion_report", False)),
    )
    _validate_selection_reason_codes(result)
    return ok_response(request, data=result)


@router.post("/context/explain")
def explain_context(request: Request, payload: ContextResolvePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    anchor = payload.anchor if isinstance(payload.anchor, dict) else {}
    lens = payload.lens if isinstance(payload.lens, dict) else {}
    budget = payload.budget if isinstance(payload.budget, dict) else {}
    result = knowledge_contract_store.resolve(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        anchor_entity_id=anchor.get("entity_id"),
        anchor_text=str(anchor.get("text") or ""),
        include_node_kinds=set(lens.get("include_node_kinds", []))
        if isinstance(lens.get("include_node_kinds"), list)
        else set(),
        include_relationship_types=set(lens.get("include_relationship_types", []))
        if isinstance(lens.get("include_relationship_types"), list)
        else set(),
        max_nodes=int(budget.get("max_nodes", 40)),
        max_edges=int(budget.get("max_edges", 80)),
        max_snippets=int(budget.get("max_snippets", 20)),
        max_tokens=int(budget.get("max_tokens", 8000)),
        debug=True,
    )
    _validate_selection_reason_codes(result)
    return ok_response(request, data=result)


@router.get("/context/channels")
def list_context_channels(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(request, data={"items": CHANNEL_PROFILES})


@router.get("/context/personas/capabilities")
def list_persona_capabilities(request: Request) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )
    personas = collaboration_store.list_personas(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id,
        enabled_only=False,
    )
    filtered = [
        _persona_capability_payload(persona)
        for persona in personas
        if _can_access_persona(auth=auth, persona=persona)
    ]
    return ok_response(request, data={"items": filtered})


@router.get("/context/personas/{persona_id}/capability")
def get_persona_capability(request: Request, persona_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )
    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    if persona.get("org_id") != auth.org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona is outside organization scope.",
                "details": {"reason_code": "STUDIO_PERSONA_ACCESS_DENIED"},
            },
        )
    if not _can_access_persona(auth=auth, persona=persona):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona access denied.",
                "details": {"reason_code": "STUDIO_PERSONA_ACCESS_DENIED"},
            },
        )
    return ok_response(request, data=_persona_capability_payload(persona))


@router.post("/context/persona-query")
async def query_persona_with_context(request: Request, payload: PersonaContextQueryPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    if not auth.org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )

    persona = collaboration_store.get_persona(tenant_id=auth.tenant_id, persona_id=payload.persona_id)
    if persona is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Persona not found.",
                "details": {"reason_code": "STUDIO_PERSONA_NOT_FOUND"},
            },
        )
    if persona.get("org_id") != auth.org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona is outside organization scope.",
                "details": {"reason_code": "STUDIO_PERSONA_ACCESS_DENIED"},
            },
        )
    if not _can_access_persona(auth=auth, persona=persona):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Persona access denied.",
                "details": {"reason_code": "STUDIO_PERSONA_ACCESS_DENIED"},
            },
        )
    if not bool(persona.get("enabled", True)):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Persona is disabled.",
                "details": {"reason_code": "STUDIO_PERSONA_DISABLED"},
            },
        )

    anchor = payload.anchor if isinstance(payload.anchor, dict) else {}
    lens = payload.lens if isinstance(payload.lens, dict) else {}
    budget = payload.budget if isinstance(payload.budget, dict) else {}
    options = payload.options if isinstance(payload.options, dict) else {}

    resolved = knowledge_contract_store.resolve(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id,
        user_id=auth.user_id,
        anchor_entity_id=anchor.get("entity_id"),
        anchor_text=str(anchor.get("text") or payload.question),
        include_node_kinds=set(lens.get("include_node_kinds", []))
        if isinstance(lens.get("include_node_kinds"), list)
        else set(),
        include_relationship_types=set(lens.get("include_relationship_types", []))
        if isinstance(lens.get("include_relationship_types"), list)
        else set(),
        max_nodes=int(budget.get("max_nodes", 40)),
        max_edges=int(budget.get("max_edges", 80)),
        max_snippets=int(budget.get("max_snippets", 20)),
        max_tokens=int(budget.get("max_tokens", 8000)),
        debug=bool(options.get("include_exclusion_report", False)),
    )
    _validate_selection_reason_codes(resolved)
    max_nodes = int(budget.get("max_nodes", 40))
    context_quality = _build_context_quality(resolved, max_nodes=max_nodes)

    context_snippet = _build_context_snippet(resolved)
    provider_id, model_id = _persona_runtime_settings(persona)
    system_prompt = compile_persona_system_prompt_resolved(
        tenant_id=auth.tenant_id,
        persona=persona,
        org_id=auth.org_id,
    )
    composed_system_prompt = (
        f"{system_prompt}\n\n"
        "You are answering with federated organizational context for AI coding and implementation support. "
        "Use context items when relevant and state uncertainty when evidence is weak."
    )
    user_content = (
        "Question:\n"
        f"{payload.question}\n\n"
        "Resolved context candidates:\n"
        f"{context_snippet}"
    )
    response = await model_gateway.generate_text(
        ModelRequest(
            system_prompt=composed_system_prompt,
            conversation_messages=[{"role": "user", "content": user_content}],
            model_profile=str(persona.get("model_profile", "reasoning-optimized") or "reasoning-optimized"),
            provider_id=provider_id,
            model_id=model_id,
            tenant_id=auth.tenant_id,
            org_id=auth.org_id,
        )
    )
    return ok_response(
        request,
        data={
            "persona": {
                "persona_id": persona.get("persona_id"),
                "name": persona.get("name"),
                "provider_id": response.provider,
                "model_id": response.model,
            },
            "answer": response.content,
            "usage": response.usage,
            "context_bundle": {
                "bundle_id": resolved.get("bundle_id"),
                "graph_version": resolved.get("graph_version"),
                "sources": resolved.get("sources", []),
                "summary": resolved.get("summary", {}),
            },
            "context_quality": context_quality,
            "validation": {
                "channel_profile_id": lens.get("channel_profile_id", "development-default"),
                "debug": bool(options.get("include_exclusion_report", False)),
            },
        },
    )


@router.get("/context/daily-summary")
def get_daily_summary(
    request: Request,
    date: str | None = Query(default=None),
    org_id: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    target_org_id = org_id or auth.org_id
    if not target_org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )

    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                    "details": {"reason_code": "DAILY_SUMMARY_DATE_INVALID"},
                },
            ) from exc
    else:
        now = datetime.now(UTC)
        day = datetime(now.year, now.month, now.day, tzinfo=UTC)
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    highlights, sections, summary = _build_daily_summary_data(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        user_id=auth.user_id,
        day_start=day_start,
        day_end=day_end,
    )
    persisted = daily_summary_store.upsert_summary(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        user_id=auth.user_id,
        summary_date=day_start.date(),
        highlights=highlights,
        sections=sections,
        stats=summary,
        metadata={"generated_by": "context.daily-summary", "version": "v1"},
    )

    return ok_response(
        request,
        data={
            "date": day_start.date().isoformat(),
            "org_id": target_org_id,
            "user_id": auth.user_id,
            "highlights": highlights,
            "sections": sections,
            "summary": summary,
            "journal_entry": persisted,
        },
    )


@router.get("/context/daily-summary/journal")
def list_daily_summary_journal(
    request: Request,
    org_id: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=120),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    target_org_id = org_id or auth.org_id
    if not target_org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )

    def _parse_day(value: str | None, reason_code: str) -> datetime.date | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                    "details": {"reason_code": reason_code},
                },
            ) from exc

    start = _parse_day(start_date, "DAILY_SUMMARY_START_DATE_INVALID")
    end = _parse_day(end_date, "DAILY_SUMMARY_END_DATE_INVALID")
    items = daily_summary_store.list_summaries(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        user_id=auth.user_id,
        start_date=start,
        end_date=end,
        limit=limit,
    )
    return ok_response(request, data={"items": items})


@router.get("/context/identity")
def get_context_identity(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    target_org_id = org_id or auth.org_id
    if not target_org_id:
        raise HTTPException(
            status_code=422,
            detail={"message": "Organization scope is required.", "details": {"reason_code": "ORG_SCOPE_REQUIRED"}},
        )
    identity = _load_user_identity_context(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        user_id=auth.user_id,
    )
    return ok_response(
        request,
        data={
            "tenant_id": auth.tenant_id,
            "user_id": auth.user_id,
            "org_id": target_org_id,
            "identity": identity,
            "cache_ttl_seconds": 60,
        },
    )


@router.post("/policy/decision")
def resolve_policy_decision(request: Request, payload: PolicyDecisionPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    target_org_id = str(payload.context.get("org_id") or auth.org_id or "")
    if not target_org_id:
        raise HTTPException(
            status_code=422,
            detail={"message": "Organization scope is required.", "details": {"reason_code": "ORG_SCOPE_REQUIRED"}},
        )
    identity = _load_user_identity_context(
        tenant_id=auth.tenant_id,
        org_id=target_org_id,
        user_id=auth.user_id,
    )
    decision = _evaluate_policy_decision(
        identity=identity,
        action=str(payload.action).strip(),
        context=payload.context if isinstance(payload.context, dict) else {},
    )
    audit_store.record_event(
        tenant_id=auth.tenant_id,
        actor_type="user",
        actor_id=auth.user_id,
        action="policy.decision.evaluate",
        resource_type=str((payload.resource or {}).get("type", "policy")) if isinstance(payload.resource, dict) else "policy",
        resource_id=str((payload.resource or {}).get("id", "")) if isinstance(payload.resource, dict) else "",
        room_id="",
        orchestration_run_id="",
        decision=("allowed" if bool(decision["allow"]) else "denied"),
        reason_code=str(decision["reason_code"]),
        policy_version="v1",
        metadata={
            "action": payload.action,
            "context": payload.context if isinstance(payload.context, dict) else {},
            "decision_basis": decision["decision_basis"],
        },
    )
    return ok_response(
        request,
        data={
            "allow": decision["allow"],
            "reason_code": decision["reason_code"],
            "decision_basis": decision["decision_basis"],
            "subject_user_id": auth.user_id,
            "org_id": target_org_id,
            "action": payload.action,
        },
    )


@router.post("/events/ingest")
def ingest_canonical_event(request: Request, payload: EventIngestPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    metadata = dict(payload.metadata)
    metadata.update(
        {
            "app_id": payload.app_id,
            "workspace_id": payload.workspace_id,
            "correlation_id": payload.correlation_id,
        }
    )
    created = audit_store.record_event(
        tenant_id=auth.tenant_id,
        actor_type="user",
        actor_id=auth.user_id,
        action=payload.event_name,
        resource_type=payload.resource_type or "event",
        resource_id=payload.resource_id,
        room_id="",
        orchestration_run_id="",
        decision="allowed",
        reason_code="EVENT_INGESTED",
        policy_version="v1",
        metadata=metadata,
    )
    return ok_response(request, data={"event": created})


@router.get("/events")
def query_canonical_events(
    request: Request,
    app_id: str | None = Query(default=None),
    workspace_id: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    events = audit_store.list_events(tenant_id=auth.tenant_id, limit=limit)
    filtered: list[dict[str, Any]] = []
    for event in events:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        if app_id and str(metadata.get("app_id", "")) != app_id:
            continue
        if workspace_id and str(metadata.get("workspace_id", "")) != workspace_id:
            continue
        if correlation_id and str(metadata.get("correlation_id", "")) != correlation_id:
            continue
        filtered.append(event)
    return ok_response(request, data={"items": filtered})


@router.get("/events/stream")
def stream_canonical_events(
    request: Request,
    app_id: str | None = Query(default=None),
    workspace_id: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> StreamingResponse:
    auth = require_authentication(request, require_org=True)
    events = audit_store.list_events(tenant_id=auth.tenant_id, limit=limit)

    filtered: list[dict[str, Any]] = []
    for event in events:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        if app_id and str(metadata.get("app_id", "")) != app_id:
            continue
        if workspace_id and str(metadata.get("workspace_id", "")) != workspace_id:
            continue
        if correlation_id and str(metadata.get("correlation_id", "")) != correlation_id:
            continue
        filtered.append(event)

    def _iter() -> Any:
        for item in reversed(filtered):
            yield f"event: canonical_event\ndata: {json.dumps(item)}\n\n"

    return StreamingResponse(_iter(), media_type="text/event-stream")


@router.post("/knowledge/documents/upload")
async def upload_knowledge_document(
    request: Request,
    org_id: str = Form(min_length=1),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    summary: str = Form(default=""),
    tags_json: str | None = Form(default=None),
    contexts_json: str | None = Form(default=None),
    facets_json: str | None = Form(default=None),
    visibility_json: str | None = Form(default=None),
    owners_json: str | None = Form(default=None),
    metadata_json: str | None = Form(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Uploaded file is empty.",
                "details": {"reason_code": "KNOWLEDGE_UPLOAD_EMPTY_FILE"},
            },
        )

    tags = _parse_json_form(tags_json, default=[], field_name="tags_json")
    contexts = _parse_json_form(contexts_json, default=[], field_name="contexts_json")
    facets = _parse_json_form(facets_json, default={}, field_name="facets_json")
    visibility = _parse_json_form(visibility_json, default={}, field_name="visibility_json")
    owners = _parse_json_form(owners_json, default=[], field_name="owners_json")
    metadata = _parse_json_form(metadata_json, default={}, field_name="metadata_json")

    if not isinstance(tags, list) or not isinstance(contexts, list):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "tags_json and contexts_json must be arrays.",
                "details": {"reason_code": "KNOWLEDGE_UPLOAD_LIST_FIELDS_INVALID"},
            },
        )
    if not isinstance(facets, dict) or not isinstance(visibility, dict) or not isinstance(metadata, dict):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "facets_json, visibility_json, and metadata_json must be objects.",
                "details": {"reason_code": "KNOWLEDGE_UPLOAD_OBJECT_FIELDS_INVALID"},
            },
        )
    if not isinstance(owners, list):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "owners_json must be an array.",
                "details": {"reason_code": "KNOWLEDGE_UPLOAD_OWNERS_INVALID"},
            },
        )

    if "scope" not in visibility:
        visibility["scope"] = "org"
    if "acl_policy_id" not in visibility:
        visibility["acl_policy_id"] = "policy-org"
    if not owners:
        owners = [{"owner_type": "user", "owner_id": auth.user_id}]

    stored = document_storage.store(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )
    extracted_text = extract_document_text(
        content=content,
        content_type=file.content_type or "application/octet-stream",
        filename=file.filename or "upload.bin",
    )

    now = datetime.now(UTC).isoformat()
    entity_id = str(uuid4())
    entity = {
        "entity_id": entity_id,
        "kind": "document",
        "kind_schema_version": "v1",
        "title": title or file.filename or "Uploaded document",
        "summary": summary,
        "tags": tags,
        "contexts": contexts,
        "facets": facets,
        "owners": owners,
        "visibility": visibility,
        "source": {
            "source_system": "upload",
            "source_id": entity_id,
            "external_ref": stored.uri,
            "source_of_truth": True,
            "dedupe_key": stored.object_key,
        },
        "content_refs": [
            {
                "ref_type": "uri",
                "ref": stored.uri,
                "snippet": extracted_text,
                "checksum": "",
            }
        ],
        "quality": {
            "confidence": 1.0,
            "verification_state": "asserted",
            "evidence_refs": [],
        },
        "lifecycle": {
            "status": "active",
            "effective_from": None,
            "effective_to": None,
            "staleness_ttl_seconds": 0,
        },
        "timestamps": {
            "created_at": now,
            "updated_at": now,
            "observed_at": now,
            "effective_from": None,
            "effective_to": None,
        },
        "kind_payload": {
            "filename": file.filename or "upload.bin",
            "content_type": file.content_type or "application/octet-stream",
            "size_bytes": stored.size_bytes,
            "storage_backend": stored.storage_backend,
            "extracted_text_length": len(extracted_text),
            "metadata": metadata,
        },
        "schema_version": "v1",
    }
    _require_entity_fields(entity)
    saved = knowledge_contract_store.upsert_entities(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        items=[entity],
    )
    return ok_response(
        request,
        data={
            "entity": saved[0],
            "storage": {
                "backend": stored.storage_backend,
                "uri": stored.uri,
                "object_key": stored.object_key,
                "size_bytes": stored.size_bytes,
            },
        },
    )
