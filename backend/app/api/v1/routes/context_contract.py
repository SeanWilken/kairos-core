from __future__ import annotations

import base64
import re
from fnmatch import fnmatch
from typing import Any
from uuid import uuid4
from datetime import UTC, datetime, timedelta
import json

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select

from app.core.auth_context import require_authentication, require_roles
from app.core.artifact_rules import evaluate_artifact_rules
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
from app.core.development_capability_inventory import build_workspace_capability_profile, resolve_capability_requirements
from app.core.knowledge_contract_store import knowledge_contract_store
from app.core.model_gateway import ModelRequest, model_gateway
from app.core.persona_prompt import compile_persona_system_prompt_resolved
from app.core.profile_presets import profile_presets_map as base_profile_presets_map
from app.core.response import ok_response
from app.core.suite_store import suite_store

router = APIRouter(tags=["knowledge-contract"])

SELECTION_REASON_CODES = {
    "explicit_reference",
    "semantic_match",
    "policy_priority",
    "graph_proximity",
    "owner_authority",
    "freshness_boost",
    "relevancy_match",
}

KNOWLEDGE_ENTITY_CONVENTIONS: dict[str, dict[str, Any]] = {
    "file": {
        "required_facets_any_of": ["path", "file_path"],
        "recommended_relationship_types": ["contains", "implements", "imports", "derived_from", "similar_to", "duplicate_of", "should_be_shared"],
    },
    "symbol": {
        "required_facets_any_of": ["symbol_name", "class_name", "function_name", "component_name"],
        "recommended_facets": ["symbol_kind", "path"],
        "recommended_relationship_types": ["belongs_to", "implements", "references", "similar_to", "duplicate_of", "extracted_from", "should_be_shared"],
    },
    "project": {
        "recommended_facets": ["project_key", "slug", "repo_name"],
        "recommended_relationship_types": ["contains", "depends_on", "supports", "related_to"],
    },
    "glossary_term": {
        "required_kind_payload_any_of": ["definition", "meaning"],
        "recommended_relationship_types": ["references", "explains", "related_to"],
    },
}

KNOWLEDGE_REUSE_RELATIONSHIP_TYPES = {
    "similar_to",
    "duplicate_of",
    "extracted_from",
    "should_be_shared",
}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_ref_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


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


class DevelopmentPolicyTargetPayload(BaseModel):
    kind: str = Field(default="path", min_length=1)
    value: str = Field(min_length=1)


class DevelopmentPolicyCheckPayload(BaseModel):
    workspace_id: str = Field(min_length=1)
    session_id: str = ""
    capability: str = Field(min_length=1)
    targets: list[DevelopmentPolicyTargetPayload] = Field(default_factory=list)
    mode: str = Field(default="build")
    context: dict[str, Any] = Field(default_factory=dict)


class EventIngestPayload(BaseModel):
    app_id: str = Field(min_length=1)
    event_name: str = Field(min_length=1)
    resource_type: str = Field(default="event")
    resource_id: str = Field(default="")
    workspace_id: str = Field(default="")
    correlation_id: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRelationshipPayload(BaseModel):
    target_entity_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    directionality: str = Field(default="directed")
    weight: float = 1.0
    facets: dict[str, Any] = Field(default_factory=dict)
    visibility: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)


class ArtifactPromotionPayload(BaseModel):
    org_id: str = Field(min_length=1)
    artifact_kind: str = Field(default="knowledge_node", min_length=1)
    artifact_subtype: str = Field(default="")
    title: str = Field(min_length=1)
    summary: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    facets: dict[str, Any] = Field(default_factory=dict)
    visibility: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    relevancy: dict[str, Any] = Field(default_factory=dict)
    relationships: list[ArtifactRelationshipPayload] = Field(default_factory=list)
    validation_rules: list[dict[str, Any]] = Field(default_factory=list)


class ArtifactRuleEvaluationPayload(BaseModel):
    artifact: dict[str, Any] = Field(default_factory=dict)
    rules: list[dict[str, Any]] = Field(default_factory=list)


class CodeIngestSymbolPayload(BaseModel):
    symbol_id: str | None = None
    name: str = Field(min_length=1)
    symbol_kind: str = Field(default="function", min_length=1)
    summary: str = ""
    signature: str = ""
    body_snippet: str = ""
    language: str = ""
    line_start: int | None = None
    line_end: int | None = None
    tags: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeIngestFilePayload(BaseModel):
    file_entity_id: str | None = None
    path: str = Field(min_length=1)
    title: str = ""
    summary: str = ""
    language: str = ""
    checksum: str = ""
    snippet: str = ""
    tags: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    symbols: list[CodeIngestSymbolPayload] = Field(default_factory=list)


class CodeIngestReuseLinkPayload(BaseModel):
    from_ref: str = Field(min_length=1)
    to_ref: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    weight: float = 1.0
    facets: dict[str, Any] = Field(default_factory=dict)


class CodeIngestProjectPayload(BaseModel):
    project_entity_id: str | None = None
    title: str = Field(min_length=1)
    summary: str = ""
    repo_name: str = ""
    repo_root: str = ""
    project_key: str = ""
    slug: str = ""
    tags: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeIngestPayload(BaseModel):
    org_id: str = Field(min_length=1)
    workspace_id: str = ""
    runner_id: str = ""
    visibility: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    project: CodeIngestProjectPayload | None = None
    files: list[CodeIngestFilePayload] = Field(default_factory=list)
    reuse_links: list[CodeIngestReuseLinkPayload] = Field(default_factory=list)


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
        "voice": _persona_voice_profile(persona),
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


def _normalize_relevancy_map(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        dimension = str(key).strip()
        if not dimension:
            continue
        if isinstance(value, (int, float)):
            normalized[dimension] = {
                "score": max(0.0, min(100.0, float(value))),
                "confidence": 100.0,
                "assignedBy": "system",
            }
            continue
        if not isinstance(value, dict):
            continue
        score_raw = value.get("score", 0.0)
        confidence_raw = value.get("confidence", 0.0)
        score = float(score_raw) if isinstance(score_raw, (int, float)) else 0.0
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0
        normalized[dimension] = {
            "score": max(0.0, min(100.0, score)),
            "confidence": max(0.0, min(100.0, confidence)),
            "assignedBy": str(value.get("assignedBy", "system")).strip() or "system",
            "assignedActorId": str(value.get("assignedActorId", "")).strip(),
            "reviewedBy": str(value.get("reviewedBy", "")).strip(),
            "lastReviewedAt": str(value.get("lastReviewedAt", "")).strip(),
            "rationale": str(value.get("rationale", "")).strip(),
        }
    return normalized


def _entity_relevancy(entity: dict[str, Any]) -> dict[str, Any]:
    raw = entity.get("relevancy")
    if isinstance(raw, dict):
        return raw
    facets = entity.get("facets", {}) if isinstance(entity.get("facets"), dict) else {}
    return facets.get("relevancy", {}) if isinstance(facets.get("relevancy"), dict) else {}


def _relevancy_score(entity: dict[str, Any], dimension: str) -> float:
    relevancy = _entity_relevancy(entity)
    value = relevancy.get(dimension)
    if isinstance(value, (int, float)):
        return max(0.0, min(100.0, float(value)))
    if isinstance(value, dict):
        score = value.get("score", 0.0)
        if isinstance(score, (int, float)):
            return max(0.0, min(100.0, float(score)))
    return 0.0


def _document_source_type(entity: dict[str, Any]) -> str:
    source = entity.get("source", {}) if isinstance(entity.get("source"), dict) else {}
    source_system = str(source.get("source_system", "")).strip().lower()
    if source_system == "upload":
        return "file"
    if source_system in {"note", "url", "generated"}:
        return source_system
    return "file"


def _document_processing_status(entity: dict[str, Any]) -> str:
    lifecycle = entity.get("lifecycle", {}) if isinstance(entity.get("lifecycle"), dict) else {}
    status = str(lifecycle.get("status", "")).strip().lower()
    if status:
        return status
    return "indexed"


def _encode_document_cursor(*, updated_at: str | None, entity_id: str) -> str:
    payload = json.dumps({"updated_at": updated_at or "", "entity_id": entity_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def _decode_document_cursor(cursor: str | None) -> tuple[str, str] | None:
    raw = str(cursor or "").strip()
    if not raw:
        return None
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Document cursor is invalid.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CURSOR_INVALID"},
            },
        )
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Document cursor is invalid.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CURSOR_INVALID"},
            },
        )
    updated_at = str(payload.get("updated_at", ""))
    entity_id = str(payload.get("entity_id", ""))
    if not entity_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Document cursor is invalid.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CURSOR_INVALID"},
            },
        )
    return updated_at, entity_id


def _normalize_knowledge_entity_summary(item: dict[str, Any]) -> dict[str, Any]:
    kind_payload = item.get("kind_payload", {}) if isinstance(item.get("kind_payload"), dict) else {}
    visibility = item.get("visibility", {}) if isinstance(item.get("visibility"), dict) else {}
    timestamps = item.get("timestamps", {}) if isinstance(item.get("timestamps"), dict) else {}
    facets = item.get("facets", {}) if isinstance(item.get("facets"), dict) else {}
    subtype = str(kind_payload.get("subtype", facets.get("subtype", ""))).strip().lower()
    quality = item.get("quality", {}) if isinstance(item.get("quality"), dict) else {}
    lifecycle = item.get("lifecycle", {}) if isinstance(item.get("lifecycle"), dict) else {}
    kind = str(item.get("kind", "")).strip().lower()
    convention_id = subtype if subtype == "glossary_term" else kind
    return {
        "entity_id": item.get("entity_id"),
        "kind": item.get("kind", ""),
        "subtype": subtype,
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "tags": item.get("tags", []),
        "contexts": item.get("contexts", []),
        "facets": facets,
        "relevancy": _entity_relevancy(item),
        "visibility": visibility,
        "visibility_scope": visibility.get("scope", ""),
        "source": item.get("source", {}),
        "confidence": quality.get("confidence", 0.0),
        "verification_state": quality.get("verification_state", "asserted"),
        "lifecycle_status": lifecycle.get("status", "active"),
        "convention_id": convention_id,
        "convention": KNOWLEDGE_ENTITY_CONVENTIONS.get(convention_id, {}),
        "updated_at": timestamps.get("updated_at"),
        "created_at": timestamps.get("created_at"),
    }


def _build_promoted_artifact_entity(
    *,
    tenant_id: str,
    org_id: str,
    user_id: str,
    payload: ArtifactPromotionPayload,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    visibility = dict(payload.visibility)
    if "scope" not in visibility:
        visibility["scope"] = "org"
    if "acl_policy_id" not in visibility:
        visibility["acl_policy_id"] = "policy-org"

    facets = dict(payload.facets)
    if payload.artifact_subtype:
        facets.setdefault("subtype", payload.artifact_subtype)

    source = dict(payload.source)
    source.setdefault("source_system", "artifact_promotion")
    source.setdefault("source_id", str(uuid4()))
    source.setdefault("source_of_truth", True)
    source.setdefault("dedupe_key", f"artifact:{payload.title}:{payload.artifact_subtype or payload.artifact_kind}")

    return {
        "entity_id": str(uuid4()),
        "kind": payload.artifact_kind,
        "kind_schema_version": "v1",
        "title": payload.title,
        "summary": payload.summary,
        "tags": payload.tags,
        "contexts": payload.contexts,
        "facets": facets,
        "owners": [{"owner_type": "user", "owner_id": user_id}],
        "visibility": visibility,
        "source": source,
        "content_refs": (
            [{"ref_type": "inline_text", "ref": "", "snippet": payload.content, "checksum": ""}]
            if payload.content.strip()
            else []
        ),
        "quality": {
            "confidence": 1.0,
            "verification_state": "asserted",
            "evidence_refs": [],
        },
        "relevancy": _normalize_relevancy_map(payload.relevancy),
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
            "subtype": payload.artifact_subtype,
            "content": payload.content,
            "metadata": payload.metadata,
        },
        "schema_version": "v1",
    }


def _code_ingest_visibility(raw: dict[str, Any]) -> dict[str, Any]:
    visibility = dict(raw) if isinstance(raw, dict) else {}
    visibility.setdefault("scope", "org")
    visibility.setdefault("acl_policy_id", "policy-org")
    return visibility


def _code_ingest_source(raw: dict[str, Any], *, default_source_id: str) -> dict[str, Any]:
    source = dict(raw) if isinstance(raw, dict) else {}
    source.setdefault("source_system", "code_ingest")
    source.setdefault("source_id", default_source_id)
    source.setdefault("source_of_truth", True)
    return source


def _code_ingest_base_entity(
    *,
    entity_id: str,
    kind: str,
    title: str,
    summary: str,
    tags: list[str],
    contexts: list[str],
    facets: dict[str, Any],
    visibility: dict[str, Any],
    source: dict[str, Any],
    content_refs: list[dict[str, Any]],
    kind_payload: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "entity_id": entity_id,
        "kind": kind,
        "kind_schema_version": "v1",
        "title": title,
        "summary": summary,
        "tags": sorted({str(item).strip() for item in tags if str(item).strip()}),
        "contexts": sorted({str(item).strip() for item in contexts if str(item).strip()}),
        "facets": facets,
        "owners": [{"owner_type": "user", "owner_id": user_id}],
        "visibility": visibility,
        "source": source,
        "content_refs": content_refs,
        "quality": {"confidence": 1.0, "verification_state": "derived", "evidence_refs": []},
        "relevancy": {},
        "lifecycle": {"status": "active", "effective_from": None, "effective_to": None, "staleness_ttl_seconds": 0},
        "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
        "kind_payload": kind_payload,
        "schema_version": "v1",
    }


def _build_code_ingest_relationship(
    *,
    from_entity_id: str,
    to_entity_id: str,
    relationship_type: str,
    directionality: str,
    weight: float,
    visibility: dict[str, Any],
    source: dict[str, Any],
    facets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "relationship_id": str(uuid4()),
        "from_entity_id": from_entity_id,
        "to_entity_id": to_entity_id,
        "relationship_type": relationship_type,
        "directionality": directionality,
        "weight": weight,
        "facets": facets or {},
        "evidence": [],
        "visibility": visibility,
        "source": source,
        "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
        "schema_version": "v1",
    }


def _symbol_ref(path: str, name: str) -> str:
    return f"{path}::{name}"


def _build_code_ingest_graph(*, auth: Any, payload: CodeIngestPayload) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    visibility = _code_ingest_visibility(payload.visibility)
    source = _code_ingest_source(payload.source, default_source_id=str(uuid4()))
    repo_name = str(payload.project.repo_name if payload.project else "").strip()
    repo_root = str(payload.project.repo_root if payload.project else "").strip()
    workspace_id = str(payload.workspace_id or "").strip()
    runner_id = str(payload.runner_id or "").strip()
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    ref_map: dict[str, str] = {}

    project_entity_id: str | None = None
    if payload.project is not None:
        project_entity_id = str(payload.project.project_entity_id or uuid4())
        project_title = str(payload.project.title).strip()
        project_facets = {
            "project_key": str(payload.project.project_key or "").strip(),
            "slug": str(payload.project.slug or "").strip(),
            "repo_name": repo_name,
            "repo_root": repo_root,
            "workspace_id": workspace_id,
            "runner_id": runner_id,
            **payload.project.metadata,
        }
        project_entity = _code_ingest_base_entity(
            entity_id=project_entity_id,
            kind="project",
            title=project_title,
            summary=str(payload.project.summary or "").strip(),
            tags=[*payload.project.tags, "code-index", "project"],
            contexts=[*payload.project.contexts, "development"],
            facets=project_facets,
            visibility=visibility,
            source={**source, "dedupe_key": f"project:{project_facets.get('project_key') or project_facets.get('slug') or repo_name or project_title}"},
            content_refs=[],
            kind_payload={"repo_name": repo_name, "repo_root": repo_root, "workspace_id": workspace_id, "runner_id": runner_id, "metadata": payload.project.metadata},
            user_id=auth.user_id,
        )
        entities.append(project_entity)
        ref_map[_normalize_ref_text(project_entity_id)] = project_entity_id
        ref_map[_normalize_ref_text(project_title)] = project_entity_id
        if repo_name:
            ref_map[_normalize_ref_text(repo_name)] = project_entity_id

    for file_item in payload.files:
        file_entity_id = str(file_item.file_entity_id or uuid4())
        path = str(file_item.path).strip()
        title = str(file_item.title or path.split("/")[-1].split("\\")[-1] or path).strip()
        file_source = {**source, "external_ref": path, "dedupe_key": f"file:{repo_name}:{path}"}
        file_entity = _code_ingest_base_entity(
            entity_id=file_entity_id,
            kind="file",
            title=title,
            summary=str(file_item.summary or "").strip(),
            tags=[*file_item.tags, "code-index", "file"],
            contexts=[*file_item.contexts, "development"],
            facets={
                "path": path,
                "file_path": path,
                "language": str(file_item.language or "").strip(),
                "checksum": str(file_item.checksum or "").strip(),
                "repo_name": repo_name,
                "repo_root": repo_root,
                "workspace_id": workspace_id,
                "runner_id": runner_id,
                **file_item.metadata,
            },
            visibility=visibility,
            source=file_source,
            content_refs=([{"ref_type": "file", "ref": path, "snippet": str(file_item.snippet or "").strip(), "checksum": str(file_item.checksum or "").strip()}] if str(file_item.snippet or "").strip() else []),
            kind_payload={"path": path, "file_path": path, "language": str(file_item.language or "").strip(), "workspace_id": workspace_id, "runner_id": runner_id, "metadata": file_item.metadata},
            user_id=auth.user_id,
        )
        entities.append(file_entity)
        ref_map[_normalize_ref_text(file_entity_id)] = file_entity_id
        ref_map[_normalize_ref_text(path)] = file_entity_id
        ref_map[_normalize_ref_text(title)] = file_entity_id
        if project_entity_id:
            relationships.append(
                _build_code_ingest_relationship(
                    from_entity_id=project_entity_id,
                    to_entity_id=file_entity_id,
                    relationship_type="contains",
                    directionality="directed",
                    weight=1.0,
                    visibility=visibility,
                    source=source,
                    facets={"workspace_id": workspace_id, "runner_id": runner_id},
                )
            )
        for symbol_item in file_item.symbols:
            symbol_entity_id = str(symbol_item.symbol_id or uuid4())
            symbol_name = str(symbol_item.name).strip()
            symbol_kind = str(symbol_item.symbol_kind or "function").strip()
            symbol_source = {**source, "external_ref": _symbol_ref(path, symbol_name), "dedupe_key": f"symbol:{repo_name}:{path}:{symbol_name}:{symbol_kind}"}
            symbol_entity = _code_ingest_base_entity(
                entity_id=symbol_entity_id,
                kind="symbol",
                title=symbol_name,
                summary=str(symbol_item.summary or "").strip(),
                tags=[*symbol_item.tags, "code-index", symbol_kind],
                contexts=[*symbol_item.contexts, "development"],
                facets={
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "path": path,
                    "file_path": path,
                    "language": str(symbol_item.language or file_item.language or "").strip(),
                    "line_start": symbol_item.line_start,
                    "line_end": symbol_item.line_end,
                    "repo_name": repo_name,
                    "repo_root": repo_root,
                    "workspace_id": workspace_id,
                    "runner_id": runner_id,
                    **symbol_item.metadata,
                },
                visibility=visibility,
                source=symbol_source,
                content_refs=([{"ref_type": "code", "ref": _symbol_ref(path, symbol_name), "snippet": str(symbol_item.body_snippet or symbol_item.signature or "").strip(), "checksum": str(file_item.checksum or "").strip()}] if str(symbol_item.body_snippet or symbol_item.signature or "").strip() else []),
                kind_payload={
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "path": path,
                    "file_path": path,
                    "signature": str(symbol_item.signature or "").strip(),
                    "line_start": symbol_item.line_start,
                    "line_end": symbol_item.line_end,
                    "workspace_id": workspace_id,
                    "runner_id": runner_id,
                    "metadata": symbol_item.metadata,
                },
                user_id=auth.user_id,
            )
            entities.append(symbol_entity)
            relationships.append(
                _build_code_ingest_relationship(
                    from_entity_id=file_entity_id,
                    to_entity_id=symbol_entity_id,
                    relationship_type="contains",
                    directionality="directed",
                    weight=1.0,
                    visibility=visibility,
                    source=source,
                    facets={"workspace_id": workspace_id, "runner_id": runner_id},
                )
            )
            relationships.append(
                _build_code_ingest_relationship(
                    from_entity_id=symbol_entity_id,
                    to_entity_id=file_entity_id,
                    relationship_type="belongs_to",
                    directionality="directed",
                    weight=1.0,
                    visibility=visibility,
                    source=source,
                    facets={"workspace_id": workspace_id, "runner_id": runner_id},
                )
            )
            if project_entity_id:
                relationships.append(
                    _build_code_ingest_relationship(
                        from_entity_id=project_entity_id,
                        to_entity_id=symbol_entity_id,
                        relationship_type="contains",
                        directionality="directed",
                        weight=1.0,
                        visibility=visibility,
                        source=source,
                        facets={"workspace_id": workspace_id, "runner_id": runner_id},
                    )
                )
            ref_map[_normalize_ref_text(symbol_entity_id)] = symbol_entity_id
            ref_map[_normalize_ref_text(symbol_name)] = symbol_entity_id
            ref_map[_normalize_ref_text(_symbol_ref(path, symbol_name))] = symbol_entity_id

    for link in payload.reuse_links:
        relationship_type = str(link.relationship_type).strip()
        if relationship_type not in KNOWLEDGE_REUSE_RELATIONSHIP_TYPES:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Unsupported code reuse relationship type.",
                    "details": {"reason_code": "KNOWLEDGE_CODE_INGEST_REUSE_RELATIONSHIP_INVALID", "relationship_type": relationship_type},
                },
            )
        from_entity_id = ref_map.get(_normalize_ref_text(link.from_ref))
        to_entity_id = ref_map.get(_normalize_ref_text(link.to_ref))
        if not from_entity_id or not to_entity_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Code ingest reuse link references could not be resolved.",
                    "details": {
                        "reason_code": "KNOWLEDGE_CODE_INGEST_REF_UNRESOLVED",
                        "from_ref": link.from_ref,
                        "to_ref": link.to_ref,
                    },
                },
            )
        relationships.append(
            _build_code_ingest_relationship(
                from_entity_id=from_entity_id,
                to_entity_id=to_entity_id,
                relationship_type=relationship_type,
                directionality=("bidirectional" if relationship_type == "similar_to" else "directed"),
                weight=float(link.weight),
                visibility=visibility,
                source=source,
                facets={**link.facets, "workspace_id": workspace_id, "runner_id": runner_id},
            )
        )
    return entities, relationships, ref_map


def _relevancy_focus_from_lens(lens: dict[str, Any]) -> dict[str, float]:
    raw = lens.get("relevancy_focus", {}) if isinstance(lens.get("relevancy_focus"), dict) else {}
    normalized: dict[str, float] = {}
    for key, value in raw.items():
        dimension = str(key).strip()
        if not dimension or not isinstance(value, (int, float)):
            continue
        weight = float(value)
        if weight <= 0:
            continue
        normalized[dimension] = weight
    return normalized


def _resolved_profile(lens: dict[str, Any]) -> dict[str, Any] | None:
    profile_id = str(lens.get("profile_id", "")).strip()
    if not profile_id:
        return None
    return _profile_presets_map().get(profile_id)


def _include_node_kinds_from_lens(lens: dict[str, Any]) -> set[str]:
    values: list[str] = []
    profile = _resolved_profile(lens)
    if isinstance(profile, dict):
        profile_kinds = profile.get("include_node_kinds", [])
        if isinstance(profile_kinds, list):
            values.extend(str(item).strip() for item in profile_kinds if str(item).strip())
    raw = lens.get("include_node_kinds", [])
    if isinstance(raw, list):
        values.extend(str(item).strip() for item in raw if str(item).strip())
    return set(values)


def _include_relationship_types_from_lens(lens: dict[str, Any]) -> set[str]:
    values: list[str] = []
    profile = _resolved_profile(lens)
    if isinstance(profile, dict):
        profile_rels = profile.get("include_relationship_types", [])
        if isinstance(profile_rels, list):
            values.extend(str(item).strip() for item in profile_rels if str(item).strip())
    raw = lens.get("include_relationship_types", [])
    if isinstance(raw, list):
        values.extend(str(item).strip() for item in raw if str(item).strip())
    return set(values)


def _merged_relevancy_focus(lens: dict[str, Any]) -> dict[str, float]:
    merged: dict[str, float] = {}
    profile = _resolved_profile(lens)
    if isinstance(profile, dict):
        preset = profile.get("relevancy_focus", {})
        if isinstance(preset, dict):
            for key, value in preset.items():
                if isinstance(value, (int, float)) and float(value) > 0:
                    merged[str(key).strip()] = float(value)
    merged.update(_relevancy_focus_from_lens(lens))
    return {key: value for key, value in merged.items() if key and value > 0}


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


def _development_operation_for_capability(capability: str) -> str:
    normalized = str(capability or "").strip().lower()
    if not normalized:
        return "read"
    if "propose" in normalized:
        return "proposal"
    if any(token in normalized for token in ("apply", "write", "upsert", "promote", "create", "checkout", "pull_latest")):
        return "write"
    if any(token in normalized for token in ("execute", "run", "install", "uninstall", "repair", "lint", "format", "diagnostics")):
        return "execute"
    return "read"


def _normalize_path_for_match(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.lstrip("./")


def _path_rule_matches(rule: dict[str, Any], target_path: str) -> bool:
    match_type = str(rule.get("match_type", rule.get("matchType", "glob"))).strip().lower() or "glob"
    pattern = _normalize_path_for_match(str(rule.get("pattern", "")))
    path = _normalize_path_for_match(target_path)
    if not pattern:
        return False
    if match_type == "exact":
        return path == pattern
    if match_type == "prefix":
        return path == pattern or path.startswith(pattern.rstrip("/") + "/")
    return fnmatch(path, pattern)


def _evaluate_development_target(*, capability: str, target: dict[str, Any], path_rules: list[dict[str, Any]]) -> dict[str, Any]:
    kind = str(target.get("kind", "path")).strip().lower() or "path"
    value = str(target.get("value", "")).strip()
    operation = _development_operation_for_capability(capability)
    if kind != "path":
        return {
            "kind": kind,
            "value": value,
            "allow": True,
            "decision": "allow",
            "reason_code": "POLICY_DEVELOPMENT_NON_PATH_TARGET_ALLOWED",
            "matched_rule": None,
        }
    matched_rule = None
    for rule in path_rules:
        if isinstance(rule, dict) and _path_rule_matches(rule, value):
            matched_rule = rule
            break
    if matched_rule is None:
        return {
            "kind": kind,
            "value": value,
            "allow": True,
            "decision": "allow",
            "reason_code": "POLICY_DEVELOPMENT_NO_MATCHING_PATH_RULE",
            "matched_rule": None,
        }
    decision_value = str(matched_rule.get(operation, "allow")).strip().lower() or "allow"
    matched_summary = {
        "path_rule_id": str(matched_rule.get("path_rule_id", matched_rule.get("pathRuleId", ""))).strip(),
        "pattern": str(matched_rule.get("pattern", "")).strip(),
        "match_type": str(matched_rule.get("match_type", matched_rule.get("matchType", "glob"))).strip() or "glob",
    }
    if decision_value == "allow":
        return {
            "kind": kind,
            "value": value,
            "allow": True,
            "decision": "allow",
            "reason_code": "POLICY_DEVELOPMENT_PATH_ALLOWED",
            "matched_rule": matched_summary,
        }
    if operation == "write" and str(matched_rule.get("proposal", "allow")).strip().lower() == "allow":
        return {
            "kind": kind,
            "value": value,
            "allow": False,
            "decision": "proposal_required",
            "reason_code": "POLICY_DEVELOPMENT_PROPOSAL_REQUIRED",
            "matched_rule": matched_summary,
        }
    return {
        "kind": kind,
        "value": value,
        "allow": False,
        "decision": "deny",
        "reason_code": "POLICY_DEVELOPMENT_PATH_DENIED",
        "matched_rule": matched_summary,
    }


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


def _has_any_non_empty(mapping: dict[str, Any], keys: list[str]) -> bool:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if value is not None and value != "" and value != [] and value != {}:
            return True
    return False


def _validate_entity_convention(item: dict[str, Any]) -> None:
    facets = item.get("facets", {}) if isinstance(item.get("facets"), dict) else {}
    kind_payload = item.get("kind_payload", {}) if isinstance(item.get("kind_payload"), dict) else {}
    kind = str(item.get("kind", "")).strip().lower()
    subtype = str(kind_payload.get("subtype", facets.get("subtype", ""))).strip().lower()
    convention_id = subtype if subtype == "glossary_term" else kind
    convention = KNOWLEDGE_ENTITY_CONVENTIONS.get(convention_id)
    if convention is None:
        return
    facet_keys = convention.get("required_facets_any_of", []) if isinstance(convention.get("required_facets_any_of", []), list) else []
    if facet_keys and not _has_any_non_empty(facets, [str(key) for key in facet_keys]):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge entity does not satisfy convention facet requirements.",
                "details": {
                    "reason_code": "KNOWLEDGE_ENTITY_CONVENTION_FACETS_REQUIRED",
                    "convention_id": convention_id,
                    "fields": facet_keys,
                },
            },
        )
    payload_keys = convention.get("required_kind_payload_any_of", []) if isinstance(convention.get("required_kind_payload_any_of", []), list) else []
    if payload_keys and not _has_any_non_empty(kind_payload, [str(key) for key in payload_keys]):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge entity does not satisfy convention payload requirements.",
                "details": {
                    "reason_code": "KNOWLEDGE_ENTITY_CONVENTION_PAYLOAD_REQUIRED",
                    "convention_id": convention_id,
                    "fields": payload_keys,
                },
            },
        )


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
    if "relevancy" in item and not isinstance(item.get("relevancy"), dict):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Knowledge entity relevancy must be an object.",
                "details": {"reason_code": "KNOWLEDGE_ENTITY_RELEVANCY_INVALID"},
            },
        )
    _validate_entity_convention(item)


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


def _persona_voice_profile(persona: dict[str, Any]) -> dict[str, Any]:
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    voice = data.get("voice", {}) if isinstance(data.get("voice"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    runtime_voice = runtime.get("voice", {}) if isinstance(runtime.get("voice"), dict) else {}
    return {**runtime_voice, **voice}


def _build_context_snippet(result: dict[str, Any], *, max_items: int = 8) -> str:
    sources = result.get("sources", []) if isinstance(result.get("sources"), list) else []
    reference_maps = result.get("reference_maps", {}) if isinstance(result.get("reference_maps"), dict) else {}
    lines: list[str] = []
    if reference_maps:
        for key in ("projects", "tasks", "files", "code", "documents", "glossary_terms"):
            values = reference_maps.get(key, [])
            if not isinstance(values, list) or not values:
                continue
            labels = [str(item.get("title", "Untitled")).strip() or "Untitled" for item in values[:3] if isinstance(item, dict)]
            if labels:
                lines.append(f"{key}: {', '.join(labels)}")
    for index, source in enumerate(sources[:max_items], start=1):
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "Untitled")).strip() or "Untitled"
        kind = str(source.get("kind", "")).strip() or "entity"
        score = source.get("score", 0)
        refs = source.get("reference_reasons", []) if isinstance(source.get("reference_reasons"), list) else []
        suffix = f" refs={';'.join(str(item) for item in refs[:2])}" if refs else ""
        lines.append(f"{index}. [{kind}] {title} (score={score}){suffix}")
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
                "similar_to",
                "duplicate_of",
                "extracted_from",
                "should_be_shared",
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


PROFILE_PRESETS: list[dict[str, Any]] = [
    {
        "profile_id": "frontend-engineer",
        "label": "Frontend Engineer",
        "description": "Bias toward UI systems, client behavior, and implementation-ready frontend knowledge.",
        "relevancy_focus": {"frontend": 1.0, "product": 0.55, "backend": 0.35},
        "include_node_kinds": ["document", "knowledge_node", "policy", "workflow", "task", "tool"],
        "include_relationship_types": ["implements", "depends_on", "supports", "uses_tool", "related_to"],
        "preferred_tools": ["knowledge_search", "code_generation", "document_create_markdown"],
        "preferred_outputs": ["markdown", "checklist", "code"],
        "voice_defaults": {"tone": "clear", "cadence": "measured"},
    },
    {
        "profile_id": "backend-engineer",
        "label": "Backend Engineer",
        "description": "Bias toward services, contracts, execution traces, runtime behavior, and operational constraints.",
        "relevancy_focus": {"backend": 1.0, "security": 0.6, "devops": 0.55, "compliance": 0.35},
        "include_node_kinds": ["document", "knowledge_node", "service", "workflow", "policy", "tool", "task"],
        "include_relationship_types": ["depends_on", "implements", "governed_by", "supports", "blocks"],
        "preferred_tools": ["knowledge_search", "code_generation", "runtime_inspect"],
        "preferred_outputs": ["markdown", "reporting", "code"],
        "voice_defaults": {"tone": "precise", "cadence": "steady"},
    },
    {
        "profile_id": "compliance-reviewer",
        "label": "Compliance Reviewer",
        "description": "Bias toward policy, regulatory, audit, and evidence-linked knowledge.",
        "relevancy_focus": {"compliance": 1.0, "regulatory": 0.95, "security": 0.7, "business": 0.35},
        "include_node_kinds": ["policy", "document", "knowledge_node", "workflow"],
        "include_relationship_types": ["governed_by", "requires_permission", "supports", "contradicts"],
        "preferred_tools": ["knowledge_search", "document_create_markdown"],
        "preferred_outputs": ["reporting", "markdown"],
        "voice_defaults": {"tone": "formal", "cadence": "deliberate"},
    },
    {
        "profile_id": "product-manager",
        "label": "Product Manager",
        "description": "Bias toward product decisions, delivery planning, customer impact, and roadmap context.",
        "relevancy_focus": {"product": 1.0, "business": 0.75, "customer_support": 0.55, "frontend": 0.4},
        "include_node_kinds": ["document", "knowledge_node", "workflow", "task", "roadmap"],
        "include_relationship_types": ["supports", "depends_on", "belongs_to", "related_to"],
        "preferred_tools": ["knowledge_search", "task_create", "document_create_markdown"],
        "preferred_outputs": ["summary", "markdown", "reporting"],
        "voice_defaults": {"tone": "encouraging", "cadence": "balanced"},
    },
    {
        "profile_id": "ai-coding-agent",
        "label": "AI Coding Agent",
        "description": "Bias toward implementation context, prior code patterns, tools, constraints, and execution safety.",
        "relevancy_focus": {"backend": 0.95, "frontend": 0.75, "devops": 0.6, "security": 0.55, "ai": 0.5},
        "include_node_kinds": ["document", "knowledge_node", "tool", "workflow", "policy", "task", "repo"],
        "include_relationship_types": ["implements", "depends_on", "uses_tool", "derived_from", "supports"],
        "preferred_tools": ["knowledge_search", "code_generation", "runtime_inspect", "task_create"],
        "preferred_outputs": ["code", "markdown", "checklist"],
        "voice_defaults": {"tone": "neutral", "cadence": "efficient"},
    },
    {
        "profile_id": "help-desk-agent",
        "label": "Help Desk Agent",
        "description": "Bias toward troubleshooting, customer issues, known fixes, SOPs, and escalation paths.",
        "relevancy_focus": {"customer_support": 1.0, "product": 0.55, "backend": 0.45, "security": 0.3},
        "include_node_kinds": ["document", "knowledge_node", "workflow", "policy", "task"],
        "include_relationship_types": ["explains", "supports", "blocks", "escalates_to", "related_to"],
        "preferred_tools": ["knowledge_search", "task_create", "document_create_markdown"],
        "preferred_outputs": ["markdown", "walkthrough", "summary"],
        "voice_defaults": {"tone": "friendly", "cadence": "calm"},
    },
    {
        "profile_id": "generalist",
        "label": "Generalist",
        "description": "Balanced multi-domain retrieval for broad support and exploratory work.",
        "relevancy_focus": {"frontend": 0.55, "backend": 0.55, "product": 0.55, "business": 0.45, "security": 0.35},
        "include_node_kinds": ["document", "knowledge_node", "workflow", "task", "policy", "tool"],
        "include_relationship_types": ["related_to", "supports", "depends_on", "explains"],
        "preferred_tools": ["knowledge_search", "document_create_markdown", "task_create"],
        "preferred_outputs": ["markdown", "summary", "reporting"],
        "voice_defaults": {"tone": "balanced", "cadence": "natural"},
    },
    {
        "profile_id": "knowledge-librarian",
        "label": "Knowledge Librarian",
        "description": "Bias toward indexing, categorization, linking, provenance, and discoverability.",
        "relevancy_focus": {"ai": 0.4, "product": 0.35, "compliance": 0.3, "backend": 0.3},
        "include_node_kinds": ["document", "knowledge_node", "note", "note_collection", "policy", "tool"],
        "include_relationship_types": ["references", "belongs_to", "derived_from", "explains", "related_to"],
        "preferred_tools": ["knowledge_search", "document_create_markdown", "relationship_create"],
        "preferred_outputs": ["markdown", "catalog", "summary"],
        "voice_defaults": {"tone": "scholarly", "cadence": "measured"},
    },
    {
        "profile_id": "relations-manager",
        "label": "Relations Manager",
        "description": "Bias toward client communications, commitments, relationship history, and deliverable follow-through.",
        "relevancy_focus": {"business": 0.9, "customer_support": 0.8, "product": 0.5, "frontend": 0.25},
        "include_node_kinds": ["document", "knowledge_node", "task", "workflow", "policy"],
        "include_relationship_types": ["supports", "depends_on", "related_to", "belongs_to"],
        "preferred_tools": ["knowledge_search", "document_create_markdown", "task_create"],
        "preferred_outputs": ["markdown", "summary", "reporting"],
        "voice_defaults": {"tone": "professional", "cadence": "warm"},
    },
    {
        "profile_id": "document-drafter",
        "label": "Document Drafter",
        "description": "Bias toward source material synthesis, structured writing, and document generation workflows.",
        "relevancy_focus": {"product": 0.4, "business": 0.35, "compliance": 0.3, "backend": 0.25},
        "include_node_kinds": ["document", "knowledge_node", "note", "policy", "workflow"],
        "include_relationship_types": ["references", "explains", "supports", "derived_from"],
        "preferred_tools": ["document_create_markdown", "knowledge_search"],
        "preferred_outputs": ["markdown", "reporting", "walkthrough"],
        "voice_defaults": {"tone": "clear", "cadence": "paced"},
    },
    {
        "profile_id": "project-manager",
        "label": "Project Manager",
        "description": "Bias toward delivery coordination, dependencies, planning, and stakeholder visibility.",
        "relevancy_focus": {"product": 0.8, "business": 0.6, "backend": 0.4, "frontend": 0.3},
        "include_node_kinds": ["task", "workflow", "document", "knowledge_node", "policy"],
        "include_relationship_types": ["depends_on", "blocks", "supports", "belongs_to"],
        "preferred_tools": ["task_create", "document_create_markdown", "knowledge_search"],
        "preferred_outputs": ["summary", "checklist", "reporting"],
        "voice_defaults": {"tone": "directive", "cadence": "steady"},
    },
    {
        "profile_id": "scrum-master",
        "label": "Scrum Master",
        "description": "Bias toward blockers, sprint coordination, flow health, and delivery rituals.",
        "relevancy_focus": {"product": 0.7, "backend": 0.45, "frontend": 0.45, "business": 0.35},
        "include_node_kinds": ["task", "workflow", "knowledge_node", "document"],
        "include_relationship_types": ["blocks", "depends_on", "supports", "related_to"],
        "preferred_tools": ["task_create", "knowledge_search", "document_create_markdown"],
        "preferred_outputs": ["checklist", "summary", "walkthrough"],
        "voice_defaults": {"tone": "facilitative", "cadence": "grounded"},
    },
]


PROFILE_ACTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "frontend-engineer": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "code_generation", "priority": 90, "mode_hint": "write"},
            {"tool_id": "document_create_markdown", "priority": 70, "mode_hint": "write", "default_output_profile": "markdown_document"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "backend-engineer": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "runtime_inspect", "priority": 95, "mode_hint": "execute"},
            {"tool_id": "code_generation", "priority": 90, "mode_hint": "write"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "image_generation": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "compliance-reviewer": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "report"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "anthropic"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "product-manager": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "task_create", "priority": 95, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "summary"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "ai-coding-agent": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "runtime_inspect", "priority": 95, "mode_hint": "execute"},
            {"tool_id": "code_generation", "priority": 90, "mode_hint": "write", "default_output_profile": "code"},
            {"tool_id": "task_create", "priority": 60, "mode_hint": "write", "default_output_profile": "task_bundle"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "image_generation": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "help-desk-agent": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "task_create", "priority": 90, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "walkthrough"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "generalist": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 85, "mode_hint": "write", "default_output_profile": "markdown_document"},
            {"tool_id": "task_create", "priority": 70, "mode_hint": "write", "default_output_profile": "task_bundle"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "knowledge-librarian": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "relationship_create", "priority": 90, "mode_hint": "write"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "catalog"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "anthropic"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "relations-manager": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 90, "mode_hint": "write", "default_output_profile": "report"},
            {"tool_id": "task_create", "priority": 80, "mode_hint": "write", "default_output_profile": "task_bundle"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "document-drafter": {
        "preferred_tool_policies": [
            {"tool_id": "document_create_markdown", "priority": 100, "mode_hint": "write", "default_output_profile": "markdown_document"},
            {"tool_id": "knowledge_search", "priority": 85, "mode_hint": "read"},
            {"tool_id": "image_generate", "priority": 40, "mode_hint": "write", "default_output_profile": "image_concept"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "anthropic"},
            "document_drafting": {"provider_id": "anthropic"},
            "image_generation": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "project-manager": {
        "preferred_tool_policies": [
            {"tool_id": "task_create", "priority": 100, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "document_create_markdown", "priority": 85, "mode_hint": "write", "default_output_profile": "report"},
            {"tool_id": "knowledge_search", "priority": 80, "mode_hint": "read"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "scrum-master": {
        "preferred_tool_policies": [
            {"tool_id": "task_create", "priority": 100, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "knowledge_search", "priority": 85, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "walkthrough"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
}


def _enrich_profile_preset(item: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(item.get("profile_id", "")).strip()
    defaults = PROFILE_ACTION_DEFAULTS.get(profile_id, {})
    return {**item, **defaults}


def _profile_presets_map() -> dict[str, dict[str, Any]]:
    return base_profile_presets_map()


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


@router.post("/knowledge/code-ingest")
def ingest_code_graph(request: Request, payload: CodeIngestPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    entities, relationships, _ref_map = _build_code_ingest_graph(auth=auth, payload=payload)
    for item in entities:
        _require_entity_fields(item)
    for item in relationships:
        _require_relationship_fields(item)
    saved_entities = knowledge_contract_store.upsert_entities(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        items=entities,
    )
    saved_relationships = knowledge_contract_store.upsert_relationships(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        items=relationships,
    )
    return ok_response(
        request,
        data={
            "workspace_id": payload.workspace_id,
            "runner_id": payload.runner_id,
            "entities_upserted": len(saved_entities),
            "relationships_upserted": len(saved_relationships),
            "project_entity_id": (saved_entities[0].get("entity_id") if payload.project is not None and saved_entities else None),
            "items": {
                "entities": saved_entities,
                "relationships": saved_relationships,
            },
        },
    )


@router.post("/knowledge/artifacts/promote")
def promote_artifact(request: Request, payload: ArtifactPromotionPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    artifact = _build_promoted_artifact_entity(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        user_id=auth.user_id,
        payload=payload,
    )
    evaluation = evaluate_artifact_rules(artifact=artifact, rules=payload.validation_rules)
    artifact = evaluation["artifact"]
    if evaluation["blocked"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Artifact promotion blocked by validation rules.",
                "details": {
                    "reason_code": "ARTIFACT_PROMOTION_BLOCKED",
                    "matched_rules": evaluation["matched_rules"],
                },
            },
        )
    _require_entity_fields(artifact)
    saved = knowledge_contract_store.upsert_entities(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        items=[artifact],
    )

    relationship_items: list[dict[str, Any]] = []
    now = datetime.now(UTC).isoformat()
    for rel in payload.relationships:
        visibility = dict(rel.visibility)
        if "scope" not in visibility:
            visibility["scope"] = "org"
        if "acl_policy_id" not in visibility:
            visibility["acl_policy_id"] = "policy-org"
        source = dict(rel.source)
        source.setdefault("source_system", "artifact_promotion")
        source.setdefault("source_id", saved[0]["entity_id"])
        source.setdefault("source_of_truth", True)
        relationship_items.append(
            {
                "relationship_id": str(uuid4()),
                "from_entity_id": saved[0]["entity_id"],
                "to_entity_id": rel.target_entity_id,
                "relationship_type": rel.relationship_type,
                "directionality": rel.directionality,
                "weight": rel.weight,
                "facets": rel.facets,
                "evidence": [],
                "visibility": visibility,
                "source": source,
                "timestamps": {
                    "created_at": now,
                    "updated_at": now,
                    "observed_at": now,
                    "effective_from": None,
                    "effective_to": None,
                },
                "schema_version": "v1",
            }
        )
    relationships: list[dict[str, Any]] = []
    if relationship_items:
        for item in relationship_items:
            _require_relationship_fields(item)
        relationships = knowledge_contract_store.upsert_relationships(
            tenant_id=auth.tenant_id,
            org_id=payload.org_id,
            items=relationship_items,
        )
    return ok_response(request, data={"artifact": saved[0], "relationships": relationships, "evaluation": evaluation})


@router.post("/knowledge/artifacts/evaluate-rules")
def evaluate_artifact_rules_endpoint(request: Request, payload: ArtifactRuleEvaluationPayload) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    artifact = dict(payload.artifact) if isinstance(payload.artifact, dict) else {}
    evaluation = evaluate_artifact_rules(artifact=artifact, rules=payload.rules)
    return ok_response(request, data=evaluation)


@router.get("/knowledge/nodes")
def list_knowledge_nodes(
    request: Request,
    org_id: str = Query(min_length=1),
    kind: str | None = Query(default=None),
    subtype: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    relevancy_dimension: str | None = Query(default=None),
    relevancy_min: float | None = Query(default=None, ge=0, le=100),
    relevancy_max: float | None = Query(default=None, ge=0, le=100),
    query: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    target_org_id = auth.org_id or org_id
    with SessionLocal() as db:
        stmt = select(KnowledgeEntityModel.entity_id).where(
            KnowledgeEntityModel.tenant_id == auth.tenant_id,
            KnowledgeEntityModel.org_id == target_org_id,
        )
        if kind:
            stmt = stmt.where(KnowledgeEntityModel.kind == kind)
        entity_ids = [
            str(value)
            for value in db.scalars(stmt.order_by(KnowledgeEntityModel.updated_at.desc()).limit(500)).all()
        ]

    normalized: list[dict[str, Any]] = []
    for candidate_id in entity_ids:
        entity = knowledge_contract_store.get_visible_entity(
            tenant_id=auth.tenant_id,
            org_id=target_org_id,
            user_id=auth.user_id,
            entity_id=candidate_id,
            bypass_acl=auth.is_global_admin,
        )
        if entity is None:
            continue
        normalized.append(_normalize_knowledge_entity_summary(entity))

    subtype_filter = str(subtype or "").strip().lower()
    tag_filter = str(tag or "").strip().lower()
    relevancy_dimension_filter = str(relevancy_dimension or "").strip()
    query_filter = str(query or "").strip().lower()
    if subtype_filter:
        normalized = [item for item in normalized if str(item.get("subtype", "")).strip().lower() == subtype_filter]
    if tag_filter:
        normalized = [item for item in normalized if tag_filter in {str(value).strip().lower() for value in item.get("tags", [])}]
    if relevancy_dimension_filter:
        if relevancy_min is not None:
            normalized = [
                item
                for item in normalized
                if _relevancy_score(item, relevancy_dimension_filter) >= relevancy_min
            ]
        if relevancy_max is not None:
            normalized = [
                item
                for item in normalized
                if _relevancy_score(item, relevancy_dimension_filter) <= relevancy_max
            ]
    if query_filter:
        def _matches(item: dict[str, Any]) -> bool:
            haystacks = [
                str(item.get("title", "")),
                str(item.get("summary", "")),
                " ".join(str(tag_value) for tag_value in item.get("tags", []) if str(tag_value).strip()),
                str(item.get("kind", "")),
                str(item.get("subtype", "")),
            ]
            return query_filter in " ".join(haystacks).lower()
        normalized = [item for item in normalized if _matches(item)]

    normalized.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("entity_id") or "")), reverse=True)
    cursor_tuple = _decode_document_cursor(cursor)
    if cursor_tuple is not None:
        cursor_updated_at, cursor_entity_id = cursor_tuple
        normalized = [
            item
            for item in normalized
            if (str(item.get("updated_at") or ""), str(item.get("entity_id") or "")) < (cursor_updated_at, cursor_entity_id)
        ]

    page = normalized[:limit]
    next_cursor = None
    if len(normalized) > limit and page:
        last = page[-1]
        next_cursor = _encode_document_cursor(
            updated_at=str(last.get("updated_at") or ""),
            entity_id=str(last.get("entity_id") or ""),
        )
    return ok_response(request, data={"items": page, "next_cursor": next_cursor})


@router.get("/knowledge/nodes/{entity_id}")
def get_knowledge_node(request: Request, entity_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    entity = knowledge_contract_store.get_visible_entity(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        entity_id=entity_id,
        bypass_acl=auth.is_global_admin,
    )
    if entity is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Knowledge node not found.",
                "details": {"reason_code": "KNOWLEDGE_NODE_NOT_FOUND"},
            },
        )
    return ok_response(request, data={"entity": entity, "summary": _normalize_knowledge_entity_summary(entity)})


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
        include_node_kinds=_include_node_kinds_from_lens(lens),
        include_relationship_types=_include_relationship_types_from_lens(lens),
        relevancy_focus=_merged_relevancy_focus(lens),
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
        include_node_kinds=_include_node_kinds_from_lens(lens),
        include_relationship_types=_include_relationship_types_from_lens(lens),
        relevancy_focus=_merged_relevancy_focus(lens),
        max_nodes=int(budget.get("max_nodes", 40)),
        max_edges=int(budget.get("max_edges", 80)),
        max_snippets=int(budget.get("max_snippets", 20)),
        max_tokens=int(budget.get("max_tokens", 8000)),
        debug=True,
    )
    _validate_selection_reason_codes(result)
    return ok_response(request, data=result)


@router.get("/knowledge/conventions")
def list_knowledge_conventions(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(
        request,
        data={
            "entity_conventions": KNOWLEDGE_ENTITY_CONVENTIONS,
            "reuse_relationship_types": sorted(KNOWLEDGE_REUSE_RELATIONSHIP_TYPES),
        },
    )


@router.get("/context/channels")
def list_context_channels(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(request, data={"items": CHANNEL_PROFILES})


@router.get("/context/profiles")
def list_context_profiles(request: Request) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    return ok_response(request, data={"items": list(_profile_presets_map().values())})


@router.get("/context/profiles/{profile_id}")
def get_context_profile(request: Request, profile_id: str) -> dict[str, Any]:
    require_authentication(request, require_org=True)
    profile = _profile_presets_map().get(str(profile_id or "").strip())
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Context profile not found.",
                "details": {"reason_code": "CONTEXT_PROFILE_NOT_FOUND"},
            },
        )
    return ok_response(request, data=profile)


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
        include_node_kinds=_include_node_kinds_from_lens(lens),
        include_relationship_types=_include_relationship_types_from_lens(lens),
        relevancy_focus=_merged_relevancy_focus(lens),
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


@router.post("/policy/development/check")
def resolve_development_policy_check(request: Request, payload: DevelopmentPolicyCheckPayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    workspace = suite_store.get_workspace(tenant_id=auth.tenant_id, workspace_id=payload.workspace_id)
    if workspace is None or str(workspace.get("org_id", "")).strip() != str(auth.org_id or "").strip():
        raise HTTPException(
            status_code=404,
            detail={"message": "Workspace not found.", "details": {"reason_code": "WORKSPACE_NOT_FOUND"}},
        )
    capability_profile = build_workspace_capability_profile(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        workspace=workspace,
    )
    capability_resolution = resolve_capability_requirements(
        capability_profile=capability_profile,
        required_capabilities=[payload.capability],
        workspace=workspace,
    )
    capability_result = capability_resolution["results"][0] if capability_resolution.get("results") else {
        "key": payload.capability,
        "status": "unavailable",
        "resolution": "missing",
        "reason_code": "DEVELOPMENT_CAPABILITY_UNAVAILABLE",
        "provenance": {},
    }
    metadata = workspace.get("metadata", {}) if isinstance(workspace.get("metadata"), dict) else {}
    policy = metadata.get("policy", {}) if isinstance(metadata.get("policy"), dict) else {}
    path_rules = policy.get("path_rules", []) if isinstance(policy.get("path_rules", []), list) else []
    target_decisions = [
        _evaluate_development_target(capability=payload.capability, target=item.model_dump(), path_rules=path_rules)
        for item in payload.targets
    ]
    targets_allow = all(bool(item.get("allow", False)) for item in target_decisions) if target_decisions else True
    allow = bool(capability_result.get("resolution") in {"ready", "proposal_only"}) and targets_allow
    primary_reason_code = str(capability_result.get("reason_code", "DEVELOPMENT_CAPABILITY_UNAVAILABLE"))
    if capability_result.get("resolution") in {"ready", "proposal_only"} and target_decisions:
        first_denied = next((item for item in target_decisions if not bool(item.get("allow", False))), None)
        if first_denied is not None:
            primary_reason_code = str(first_denied.get("reason_code", primary_reason_code))
        else:
            primary_reason_code = "POLICY_DEVELOPMENT_ALLOW"
    elif capability_result.get("resolution") == "ready" and not target_decisions:
        primary_reason_code = "POLICY_DEVELOPMENT_ALLOW"
    audit_store.record_event(
        tenant_id=auth.tenant_id,
        actor_type="user",
        actor_id=auth.user_id,
        action="policy.development.check",
        resource_type="workspace",
        resource_id=payload.workspace_id,
        room_id="",
        orchestration_run_id="",
        decision=("allowed" if allow else "denied"),
        reason_code=primary_reason_code,
        policy_version="v1",
        metadata={
            "session_id": payload.session_id,
            "capability": payload.capability,
            "mode": payload.mode,
            "targets": [item.model_dump() for item in payload.targets],
            "capability_result": capability_result,
            "target_decisions": target_decisions,
            "context": payload.context,
        },
    )
    return ok_response(
        request,
        data={
            "allow": allow,
            "reason_code": primary_reason_code,
            "workspace_id": payload.workspace_id,
            "session_id": payload.session_id,
            "capability": payload.capability,
            "mode": payload.mode,
            "capability_result": capability_result,
            "target_decisions": target_decisions,
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


@router.get("/knowledge/documents")
def list_knowledge_documents(
    request: Request,
    org_id: str = Query(min_length=1),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    visibility_scope: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = knowledge_contract_store.list_visible_entities(
        tenant_id=auth.tenant_id,
        org_id=org_id,
        user_id=auth.user_id,
        kind="document",
        limit=500,
        bypass_acl=auth.is_global_admin,
    )

    normalized: list[dict[str, Any]] = []
    for item in items:
        kind_payload = item.get("kind_payload", {}) if isinstance(item.get("kind_payload"), dict) else {}
        content_refs = item.get("content_refs", []) if isinstance(item.get("content_refs"), list) else []
        first_ref = content_refs[0] if content_refs and isinstance(content_refs[0], dict) else {}
        normalized_item = {
            "document_id": item.get("entity_id"),
            "entity_id": item.get("entity_id"),
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "tags": item.get("tags", []),
            "visibility": item.get("visibility", {}),
            "visibility_scope": (item.get("visibility", {}) or {}).get("scope", "") if isinstance(item.get("visibility"), dict) else "",
            "source_type": _document_source_type(item),
            "processing_status": _document_processing_status(item),
            "content_type": kind_payload.get("content_type", "application/octet-stream"),
            "filename": kind_payload.get("filename", item.get("title", "document")),
            "size_bytes": kind_payload.get("size_bytes", 0),
            "storage_backend": kind_payload.get("storage_backend", ""),
            "snippet": first_ref.get("snippet", ""),
            "updated_at": item.get("timestamps", {}).get("updated_at") if isinstance(item.get("timestamps"), dict) else None,
            "created_at": item.get("timestamps", {}).get("created_at") if isinstance(item.get("timestamps"), dict) else None,
        }
        normalized.append(normalized_item)

    status_filter = str(status or "").strip().lower()
    source_type_filter = str(source_type or "").strip().lower()
    visibility_filter = str(visibility_scope or "").strip().lower()
    query_filter = str(query or "").strip().lower()
    if status_filter:
        normalized = [item for item in normalized if str(item.get("processing_status", "")).strip().lower() == status_filter]
    if source_type_filter:
        normalized = [item for item in normalized if str(item.get("source_type", "")).strip().lower() == source_type_filter]
    if visibility_filter:
        normalized = [item for item in normalized if str(item.get("visibility_scope", "")).strip().lower() == visibility_filter]
    if query_filter:
        def _matches(item: dict[str, Any]) -> bool:
            haystacks = [
                str(item.get("title", "")),
                str(item.get("summary", "")),
                str(item.get("filename", "")),
                str(item.get("snippet", "")),
                " ".join(str(tag) for tag in item.get("tags", []) if str(tag).strip()),
            ]
            return query_filter in " ".join(haystacks).lower()
        normalized = [item for item in normalized if _matches(item)]

    normalized.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("entity_id") or "")), reverse=True)
    cursor_tuple = _decode_document_cursor(cursor)
    if cursor_tuple is not None:
        cursor_updated_at, cursor_entity_id = cursor_tuple
        normalized = [
            item
            for item in normalized
            if (str(item.get("updated_at") or ""), str(item.get("entity_id") or "")) < (cursor_updated_at, cursor_entity_id)
        ]

    page = normalized[:limit]
    next_cursor = None
    if len(normalized) > limit and page:
        last = page[-1]
        next_cursor = _encode_document_cursor(
            updated_at=str(last.get("updated_at") or ""),
            entity_id=str(last.get("entity_id") or ""),
        )
    return ok_response(request, data={"items": page, "next_cursor": next_cursor})


@router.get("/knowledge/documents/{document_id}")
def get_knowledge_document(request: Request, document_id: str) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    entity = knowledge_contract_store.get_visible_entity(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        entity_id=document_id,
        bypass_acl=auth.is_global_admin,
    )
    if entity is None or str(entity.get("kind", "")) != "document":
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Document not found.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_NOT_FOUND"},
            },
        )
    kind_payload = entity.get("kind_payload", {}) if isinstance(entity.get("kind_payload"), dict) else {}
    return ok_response(
        request,
        data={
            "document_id": entity.get("entity_id"),
            "entity": entity,
            "document": {
                "filename": kind_payload.get("filename", entity.get("title", "document")),
                "content_type": kind_payload.get("content_type", "application/octet-stream"),
                "size_bytes": kind_payload.get("size_bytes", 0),
                "storage_backend": kind_payload.get("storage_backend", ""),
            },
        },
    )


@router.get("/knowledge/documents/{document_id}/content")
def get_knowledge_document_content(request: Request, document_id: str) -> Response:
    auth = require_authentication(request, require_org=True)
    entity = knowledge_contract_store.get_visible_entity(
        tenant_id=auth.tenant_id,
        org_id=auth.org_id or "",
        user_id=auth.user_id,
        entity_id=document_id,
        bypass_acl=auth.is_global_admin,
    )
    if entity is None or str(entity.get("kind", "")) != "document":
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Document not found.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_NOT_FOUND"},
            },
        )

    content_refs = entity.get("content_refs", []) if isinstance(entity.get("content_refs"), list) else []
    first_ref = content_refs[0] if content_refs and isinstance(content_refs[0], dict) else None
    if not isinstance(first_ref, dict):
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Document content reference not found.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CONTENT_NOT_FOUND"},
            },
        )

    uri = str(first_ref.get("ref", "")).strip()
    if not uri:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Document content reference not found.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CONTENT_NOT_FOUND"},
            },
        )

    kind_payload = entity.get("kind_payload", {}) if isinstance(entity.get("kind_payload"), dict) else {}
    content_type = str(kind_payload.get("content_type", "application/octet-stream") or "application/octet-stream")
    filename = str(kind_payload.get("filename", entity.get("title", "document")) or "document")
    try:
        content = document_storage.load(uri=uri)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Stored document content was not found.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CONTENT_NOT_FOUND"},
            },
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to load stored document content.",
                "details": {"reason_code": "KNOWLEDGE_DOCUMENT_CONTENT_LOAD_FAILED"},
            },
        ) from error

    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    return Response(content=content, media_type=content_type, headers=headers)
