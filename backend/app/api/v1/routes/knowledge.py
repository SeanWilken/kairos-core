from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication, require_roles
from app.core.knowledge_index_store import knowledge_index_store
from app.core.response import ok_response

router = APIRouter(prefix="/knowledge", tags=["knowledge-index"])


class KnowledgeDomainCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    summary: str = ""
    parent_domain_id: str | None = None
    sensitivity_default: str = "internal"
    tags: list[str] = Field(default_factory=list)


class KnowledgeNodeCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    domain_id: str | None = None
    node_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    sensitivity: str = "internal"
    source_type: str = ""
    source_id: str = ""
    owner_user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    confidence: float = 1.0


class KnowledgeEdgeCreatePayload(BaseModel):
    org_id: str = Field(min_length=1)
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    summary: str = ""
    visibility: str = "internal"
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/domains")
def create_knowledge_domain(request: Request, payload: KnowledgeDomainCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    item = knowledge_index_store.create_domain(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        name=payload.name,
        summary=payload.summary,
        parent_domain_id=payload.parent_domain_id,
        sensitivity_default=payload.sensitivity_default,
        tags=payload.tags,
    )
    return ok_response(request, data=item)


@router.get("/domains")
def list_knowledge_domains(request: Request, org_id: str = Query(min_length=1)) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = knowledge_index_store.list_domains(tenant_id=auth.tenant_id, org_id=org_id)
    return ok_response(request, data={"items": items})


@router.post("/nodes")
def create_knowledge_node(request: Request, payload: KnowledgeNodeCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    item = knowledge_index_store.create_node(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        domain_id=payload.domain_id,
        node_type=payload.node_type,
        title=payload.title,
        summary=payload.summary,
        description=payload.description,
        tags=payload.tags,
        sensitivity=payload.sensitivity,
        source_type=payload.source_type,
        source_id=payload.source_id,
        owner_user_id=payload.owner_user_id,
        metadata=payload.metadata,
        status=payload.status,
        confidence=payload.confidence,
    )
    return ok_response(request, data=item)


@router.get("/nodes")
def list_knowledge_nodes(
    request: Request,
    org_id: str = Query(min_length=1),
    domain_id: str | None = None,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = knowledge_index_store.list_nodes(tenant_id=auth.tenant_id, org_id=org_id, domain_id=domain_id)
    return ok_response(request, data={"items": items})


@router.post("/edges")
def create_knowledge_edge(request: Request, payload: KnowledgeEdgeCreatePayload) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    require_roles(auth, {"owner", "admin"})
    item = knowledge_index_store.create_edge(
        tenant_id=auth.tenant_id,
        org_id=payload.org_id,
        from_node_id=payload.from_node_id,
        to_node_id=payload.to_node_id,
        relationship_type=payload.relationship_type,
        summary=payload.summary,
        visibility=payload.visibility,
        confidence=payload.confidence,
        metadata=payload.metadata,
        created_by_user_id=auth.user_id,
    )
    return ok_response(request, data=item)


@router.get("/edges")
def list_knowledge_edges(
    request: Request,
    org_id: str = Query(min_length=1),
    node_id: str | None = None,
) -> dict[str, Any]:
    auth = require_authentication(request, require_org=True)
    items = knowledge_index_store.list_edges(tenant_id=auth.tenant_id, org_id=org_id, node_id=node_id)
    return ok_response(request, data={"items": items})
