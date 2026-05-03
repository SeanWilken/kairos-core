from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.db_models import KnowledgeDomainModel, KnowledgeEdgeModel, KnowledgeNodeModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class KnowledgeIndexStore:
    def _to_domain_dict(self, model: KnowledgeDomainModel) -> dict[str, Any]:
        tags: list[str] = []
        try:
            loaded = json.loads(model.tags_json)
            if isinstance(loaded, list):
                tags = [str(item) for item in loaded]
        except Exception:
            tags = []
        return {
            "domain_id": model.domain_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "name": model.name,
            "summary": model.summary,
            "parent_domain_id": model.parent_domain_id,
            "sensitivity_default": model.sensitivity_default,
            "tags": tags,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_node_dict(self, model: KnowledgeNodeModel) -> dict[str, Any]:
        tags: list[str] = []
        metadata: dict[str, Any] = {}
        try:
            loaded_tags = json.loads(model.tags_json)
            if isinstance(loaded_tags, list):
                tags = [str(item) for item in loaded_tags]
        except Exception:
            tags = []
        try:
            loaded_meta = json.loads(model.metadata_json)
            if isinstance(loaded_meta, dict):
                metadata = loaded_meta
        except Exception:
            metadata = {}
        return {
            "node_id": model.node_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "domain_id": model.domain_id,
            "node_type": model.node_type,
            "title": model.title,
            "summary": model.summary,
            "description": model.description,
            "tags": tags,
            "sensitivity": model.sensitivity,
            "source_type": model.source_type,
            "source_id": model.source_id,
            "owner_user_id": model.owner_user_id,
            "metadata": metadata,
            "status": model.status,
            "confidence": model.confidence,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_edge_dict(self, model: KnowledgeEdgeModel) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        try:
            loaded_meta = json.loads(model.metadata_json)
            if isinstance(loaded_meta, dict):
                metadata = loaded_meta
        except Exception:
            metadata = {}
        return {
            "edge_id": model.edge_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "from_node_id": model.from_node_id,
            "to_node_id": model.to_node_id,
            "relationship_type": model.relationship_type,
            "summary": model.summary,
            "visibility": model.visibility,
            "confidence": model.confidence,
            "metadata": metadata,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def create_domain(self, *, tenant_id: str, org_id: str, name: str, summary: str, parent_domain_id: str | None, sensitivity_default: str, tags: list[str]) -> dict[str, Any]:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            model = KnowledgeDomainModel(
                domain_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=name,
                summary=summary,
                parent_domain_id=parent_domain_id,
                sensitivity_default=sensitivity_default,
                tags_json=json.dumps(tags),
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_domain_dict(model)

    def list_domains(self, *, tenant_id: str, org_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(KnowledgeDomainModel)
                .where(KnowledgeDomainModel.tenant_id == tenant_id, KnowledgeDomainModel.org_id == org_id)
                .order_by(KnowledgeDomainModel.created_at.asc())
            ).all()
            return [self._to_domain_dict(item) for item in rows]

    def create_node(self, *, tenant_id: str, org_id: str, domain_id: str | None, node_type: str, title: str, summary: str, description: str, tags: list[str], sensitivity: str, source_type: str, source_id: str, owner_user_id: str | None, metadata: dict[str, Any], status: str, confidence: float) -> dict[str, Any]:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            model = KnowledgeNodeModel(
                node_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                domain_id=domain_id,
                node_type=node_type,
                title=title,
                summary=summary,
                description=description,
                tags_json=json.dumps(tags),
                sensitivity=sensitivity,
                source_type=source_type,
                source_id=source_id,
                owner_user_id=owner_user_id,
                metadata_json=json.dumps(metadata),
                status=status,
                confidence=confidence,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_node_dict(model)

    def list_nodes(self, *, tenant_id: str, org_id: str, domain_id: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(KnowledgeNodeModel).where(
                KnowledgeNodeModel.tenant_id == tenant_id,
                KnowledgeNodeModel.org_id == org_id,
            )
            if domain_id:
                stmt = stmt.where(KnowledgeNodeModel.domain_id == domain_id)
            rows = db.scalars(stmt.order_by(KnowledgeNodeModel.created_at.asc())).all()
            return [self._to_node_dict(item) for item in rows]

    def create_edge(self, *, tenant_id: str, org_id: str, from_node_id: str, to_node_id: str, relationship_type: str, summary: str, visibility: str, confidence: float, metadata: dict[str, Any], created_by_user_id: str | None) -> dict[str, Any]:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            model = KnowledgeEdgeModel(
                edge_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                relationship_type=relationship_type,
                summary=summary,
                visibility=visibility,
                confidence=confidence,
                metadata_json=json.dumps(metadata),
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_edge_dict(model)

    def list_edges(self, *, tenant_id: str, org_id: str, node_id: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(KnowledgeEdgeModel).where(
                KnowledgeEdgeModel.tenant_id == tenant_id,
                KnowledgeEdgeModel.org_id == org_id,
            )
            if node_id:
                stmt = stmt.where(
                    (KnowledgeEdgeModel.from_node_id == node_id) | (KnowledgeEdgeModel.to_node_id == node_id)
                )
            rows = db.scalars(stmt.order_by(KnowledgeEdgeModel.created_at.asc())).all()
            return [self._to_edge_dict(item) for item in rows]


knowledge_index_store = KnowledgeIndexStore()
