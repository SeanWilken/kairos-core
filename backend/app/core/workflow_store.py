from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import StudioWorkflowDefinitionModel, WorkflowReviewQueueModel, WorkflowRunModel


def _dt_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


class WorkflowStore:
    def _to_definition_dict(self, model: StudioWorkflowDefinitionModel) -> dict[str, Any]:
        return {
            "workflow_id": model.workflow_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "name": model.name,
            "description": model.description,
            "spec_version": model.spec_version,
            "trigger": json.loads(model.trigger_json or "{}"),
            "nodes": json.loads(model.nodes_json or "[]"),
            "edges": json.loads(model.edges_json or "[]"),
            "logic_rules": json.loads(model.logic_rules_json or "[]"),
            "policy": json.loads(model.policy_json or "{}"),
            "metadata": json.loads(model.metadata_json or "{}"),
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_review_dict(self, model: WorkflowReviewQueueModel) -> dict[str, Any]:
        return {
            "review_id": model.review_id,
            "workflow_id": model.workflow_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "run_id": model.run_id,
            "node_id": model.node_id,
            "title": model.title,
            "summary": model.summary,
            "status": model.status,
            "reason_code": model.reason_code,
            "requested_by": model.requested_by_user_id,
            "requested_at": _dt_iso(model.requested_at),
            "resolved_by": model.resolved_by_user_id,
            "resolved_at": _dt_iso(model.resolved_at),
            "context": json.loads(model.context_json or "{}"),
        }

    def _to_run_dict(self, model: WorkflowRunModel) -> dict[str, Any]:
        return {
            "run_id": model.run_id,
            "workflow_id": model.workflow_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "status": model.status,
            "artifact": json.loads(model.artifact_json or "{}"),
            "review_context": json.loads(model.review_context_json or "{}"),
            "matched_rules": json.loads(model.matched_rules_json or "[]"),
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def create_definition(
        self,
        *,
        tenant_id: str,
        org_id: str,
        name: str,
        description: str,
        trigger: dict[str, Any],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        logic_rules: list[dict[str, Any]],
        policy: dict[str, Any],
        metadata: dict[str, Any],
        created_by_user_id: str,
        spec_version: str = "v0.3",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = StudioWorkflowDefinitionModel(
                workflow_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=name,
                description=description,
                spec_version=spec_version,
                trigger_json=json.dumps(trigger),
                nodes_json=json.dumps(nodes),
                edges_json=json.dumps(edges),
                logic_rules_json=json.dumps(logic_rules),
                policy_json=json.dumps(policy),
                metadata_json=json.dumps(metadata),
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_definition_dict(row)

    def list_definitions(self, *, tenant_id: str, org_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioWorkflowDefinitionModel)
                .where(StudioWorkflowDefinitionModel.tenant_id == tenant_id)
                .where(StudioWorkflowDefinitionModel.org_id == org_id)
                .order_by(desc(StudioWorkflowDefinitionModel.updated_at))
                .limit(limit)
            ).all()
            return [self._to_definition_dict(row) for row in rows]

    def get_definition(self, *, tenant_id: str, workflow_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioWorkflowDefinitionModel)
                .where(StudioWorkflowDefinitionModel.tenant_id == tenant_id)
                .where(StudioWorkflowDefinitionModel.workflow_id == workflow_id)
            )
            return self._to_definition_dict(row) if row else None

    def update_definition(
        self,
        *,
        tenant_id: str,
        workflow_id: str,
        name: str | None = None,
        description: str | None = None,
        trigger: dict[str, Any] | None = None,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
        logic_rules: list[dict[str, Any]] | None = None,
        policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioWorkflowDefinitionModel)
                .where(StudioWorkflowDefinitionModel.tenant_id == tenant_id)
                .where(StudioWorkflowDefinitionModel.workflow_id == workflow_id)
            )
            if row is None:
                return None
            if name is not None:
                row.name = name
            if description is not None:
                row.description = description
            if trigger is not None:
                row.trigger_json = json.dumps(trigger)
            if nodes is not None:
                row.nodes_json = json.dumps(nodes)
            if edges is not None:
                row.edges_json = json.dumps(edges)
            if logic_rules is not None:
                row.logic_rules_json = json.dumps(logic_rules)
            if policy is not None:
                row.policy_json = json.dumps(policy)
            if metadata is not None:
                row.metadata_json = json.dumps(metadata)
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_definition_dict(row)

    def create_review_item(
        self,
        *,
        tenant_id: str,
        org_id: str,
        workflow_id: str,
        run_id: str,
        node_id: str,
        title: str,
        summary: str,
        reason_code: str,
        requested_by_user_id: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = WorkflowReviewQueueModel(
                review_id=str(uuid4()),
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                org_id=org_id,
                run_id=run_id,
                node_id=node_id,
                title=title,
                summary=summary,
                status="pending",
                reason_code=reason_code,
                requested_by_user_id=requested_by_user_id,
                resolved_by_user_id=None,
                context_json=json.dumps(context),
                requested_at=now,
                resolved_at=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_review_dict(row)

    def list_review_items(self, *, tenant_id: str, org_id: str, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = (
                select(WorkflowReviewQueueModel)
                .where(WorkflowReviewQueueModel.tenant_id == tenant_id)
                .where(WorkflowReviewQueueModel.org_id == org_id)
            )
            if status:
                stmt = stmt.where(WorkflowReviewQueueModel.status == status)
            rows = db.scalars(stmt.order_by(desc(WorkflowReviewQueueModel.requested_at)).limit(limit)).all()
            return [self._to_review_dict(row) for row in rows]

    def create_run(
        self,
        *,
        tenant_id: str,
        org_id: str,
        workflow_id: str,
        status: str,
        artifact: dict[str, Any],
        review_context: dict[str, Any],
        matched_rules: list[dict[str, Any]],
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = WorkflowRunModel(
                run_id=str(uuid4()),
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                org_id=org_id,
                status=status,
                artifact_json=json.dumps(artifact),
                review_context_json=json.dumps(review_context),
                matched_rules_json=json.dumps(matched_rules),
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_run_dict(row)

    def get_run(self, *, tenant_id: str, run_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(WorkflowRunModel)
                .where(WorkflowRunModel.tenant_id == tenant_id)
                .where(WorkflowRunModel.run_id == run_id)
            )
            return self._to_run_dict(row) if row else None

    def list_runs(self, *, tenant_id: str, workflow_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(WorkflowRunModel)
                .where(WorkflowRunModel.tenant_id == tenant_id)
                .where(WorkflowRunModel.workflow_id == workflow_id)
                .order_by(desc(WorkflowRunModel.created_at))
                .limit(limit)
            ).all()
            return [self._to_run_dict(row) for row in rows]

    def update_run_status(self, *, tenant_id: str, run_id: str, status: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(WorkflowRunModel)
                .where(WorkflowRunModel.tenant_id == tenant_id)
                .where(WorkflowRunModel.run_id == run_id)
            )
            if row is None:
                return None
            row.status = status
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_run_dict(row)

    def update_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
        status: str | None = None,
        artifact: dict[str, Any] | None = None,
        review_context: dict[str, Any] | None = None,
        matched_rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(WorkflowRunModel)
                .where(WorkflowRunModel.tenant_id == tenant_id)
                .where(WorkflowRunModel.run_id == run_id)
            )
            if row is None:
                return None
            if status is not None:
                row.status = status
            if artifact is not None:
                row.artifact_json = json.dumps(artifact)
            if review_context is not None:
                row.review_context_json = json.dumps(review_context)
            if matched_rules is not None:
                row.matched_rules_json = json.dumps(matched_rules)
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_run_dict(row)

    def resolve_review_item(
        self,
        *,
        tenant_id: str,
        review_id: str,
        decision: str,
        resolved_by_user_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(WorkflowReviewQueueModel)
                .where(WorkflowReviewQueueModel.tenant_id == tenant_id)
                .where(WorkflowReviewQueueModel.review_id == review_id)
            )
            if row is None:
                return None
            row.status = decision
            row.resolved_by_user_id = resolved_by_user_id
            row.resolved_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_review_dict(row)


workflow_store = WorkflowStore()
