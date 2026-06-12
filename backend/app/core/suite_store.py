from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import AppAccessGrantModel, GeneratedArtifactModel, WorkspaceRecordModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _load_json(raw: str, default: Any) -> Any:
    try:
        value = json.loads(raw)
        return value
    except Exception:
        return default


class SuiteStore:
    def _workspace_dict(self, model: WorkspaceRecordModel) -> dict[str, Any]:
        return {
            "workspace_id": model.workspace_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "name": model.name,
            "kind": model.kind,
            "description": model.description,
            "status": model.status,
            "schema_version": model.schema_version,
            "state_version": model.state_version,
            "revision": model.revision,
            "thread_binding": _load_json(model.thread_binding_json or "{}", {}),
            "state": _load_json(model.state_json or "{}", {}),
            "metadata": _load_json(model.metadata_json or "{}", {}),
            "created_by_user_id": model.created_by_user_id,
            "archived_at": _dt_iso(model.archived_at) if model.archived_at else None,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def create_workspace(
        self,
        *,
        tenant_id: str,
        org_id: str,
        name: str,
        kind: str,
        description: str,
        thread_binding: dict[str, Any],
        state: dict[str, Any],
        metadata: dict[str, Any],
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        model = WorkspaceRecordModel(
            workspace_id=str(uuid4()),
            tenant_id=tenant_id,
            org_id=org_id,
            name=name,
            kind=kind,
            description=description,
            thread_binding_json=json.dumps(thread_binding),
            state_json=json.dumps(state),
            metadata_json=json.dumps(metadata),
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        with SessionLocal() as db:
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._workspace_dict(model)

    def list_workspaces(self, *, tenant_id: str, org_id: str, status: str = "active") -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(WorkspaceRecordModel).where(
                WorkspaceRecordModel.tenant_id == tenant_id,
                WorkspaceRecordModel.org_id == org_id,
            )
            if status:
                stmt = stmt.where(WorkspaceRecordModel.status == status)
            rows = db.scalars(stmt.order_by(desc(WorkspaceRecordModel.updated_at))).all()
            return [self._workspace_dict(row) for row in rows]

    def get_workspace(self, *, tenant_id: str, workspace_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(WorkspaceRecordModel).where(
                    WorkspaceRecordModel.tenant_id == tenant_id,
                    WorkspaceRecordModel.workspace_id == workspace_id,
                )
            )
            return self._workspace_dict(row) if row else None

    def update_workspace(self, *, tenant_id: str, workspace_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = db.scalar(
                select(WorkspaceRecordModel).where(
                    WorkspaceRecordModel.tenant_id == tenant_id,
                    WorkspaceRecordModel.workspace_id == workspace_id,
                )
            )
            if row is None:
                return None
            if "name" in patch:
                row.name = str(patch.get("name") or row.name)
            if "description" in patch:
                row.description = str(patch.get("description") or "")
            if "status" in patch:
                row.status = str(patch.get("status") or row.status)
            if "thread_binding" in patch and isinstance(patch.get("thread_binding"), dict):
                row.thread_binding_json = json.dumps(patch["thread_binding"])
            if "state" in patch and isinstance(patch.get("state"), dict):
                row.state_json = json.dumps(patch["state"])
                row.state_version = max(int(row.state_version or 1) + 1, 1)
            if "metadata" in patch and isinstance(patch.get("metadata"), dict):
                row.metadata_json = json.dumps(patch["metadata"])
            row.revision = max(int(row.revision or 1) + 1, 1)
            row.updated_at = now
            if row.status == "archived" and row.archived_at is None:
                row.archived_at = now
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._workspace_dict(row)

    def _grant_dict(self, model: AppAccessGrantModel) -> dict[str, Any]:
        return {
            "grant_id": model.grant_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "user_id": model.user_id,
            "app_id": model.app_id,
            "role": model.role,
            "feature_flags": _load_json(model.feature_flags_json or "[]", []),
            "status": model.status,
            "granted_by_user_id": model.granted_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def upsert_app_access_grant(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        app_id: str,
        role: str,
        feature_flags: list[str],
        status: str,
        granted_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = db.scalar(
                select(AppAccessGrantModel).where(
                    AppAccessGrantModel.org_id == org_id,
                    AppAccessGrantModel.user_id == user_id,
                    AppAccessGrantModel.app_id == app_id,
                )
            )
            if row is None:
                row = AppAccessGrantModel(
                    grant_id=str(uuid4()),
                    tenant_id=tenant_id,
                    org_id=org_id,
                    user_id=user_id,
                    app_id=app_id,
                    role=role,
                    feature_flags_json=json.dumps(feature_flags),
                    status=status,
                    granted_by_user_id=granted_by_user_id,
                    created_at=now,
                    updated_at=now,
                )
            else:
                row.role = role
                row.feature_flags_json = json.dumps(feature_flags)
                row.status = status
                row.granted_by_user_id = granted_by_user_id
                row.updated_at = now
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._grant_dict(row)

    def list_app_access_grants(self, *, tenant_id: str, org_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(AppAccessGrantModel).where(
                AppAccessGrantModel.tenant_id == tenant_id,
                AppAccessGrantModel.org_id == org_id,
            )
            if user_id:
                stmt = stmt.where(AppAccessGrantModel.user_id == user_id)
            rows = db.scalars(stmt.order_by(desc(AppAccessGrantModel.updated_at))).all()
            return [self._grant_dict(row) for row in rows]

    def _artifact_dict(self, model: GeneratedArtifactModel) -> dict[str, Any]:
        return {
            "artifact_id": model.artifact_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "channel_id": model.channel_id,
            "workspace_id": model.workspace_id,
            "orchestration_run_id": model.orchestration_run_id,
            "message_id": model.message_id,
            "artifact_type": model.artifact_type,
            "producer_type": model.producer_type,
            "producer_id": model.producer_id,
            "title": model.title,
            "content": model.content,
            "metadata": _load_json(model.metadata_json or "{}", {}),
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
        }

    def create_artifact(
        self,
        *,
        tenant_id: str,
        org_id: str,
        channel_id: str | None,
        workspace_id: str | None,
        orchestration_run_id: str,
        message_id: str,
        artifact_type: str,
        producer_type: str,
        producer_id: str,
        title: str,
        content: str,
        metadata: dict[str, Any],
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = GeneratedArtifactModel(
            artifact_id=str(uuid4()),
            tenant_id=tenant_id,
            org_id=org_id,
            channel_id=channel_id,
            workspace_id=workspace_id,
            orchestration_run_id=orchestration_run_id,
            message_id=message_id,
            artifact_type=artifact_type,
            producer_type=producer_type,
            producer_id=producer_id,
            title=title,
            content=content,
            metadata_json=json.dumps(metadata),
            created_by_user_id=created_by_user_id,
            created_at=now,
        )
        with SessionLocal() as db:
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._artifact_dict(row)

    def list_artifacts(
        self,
        *,
        tenant_id: str,
        org_id: str,
        channel_id: str | None = None,
        workspace_id: str | None = None,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(GeneratedArtifactModel).where(
                GeneratedArtifactModel.tenant_id == tenant_id,
                GeneratedArtifactModel.org_id == org_id,
            )
            if channel_id:
                stmt = stmt.where(GeneratedArtifactModel.channel_id == channel_id)
            if workspace_id:
                stmt = stmt.where(GeneratedArtifactModel.workspace_id == workspace_id)
            if artifact_type:
                stmt = stmt.where(GeneratedArtifactModel.artifact_type == artifact_type)
            rows = db.scalars(
                stmt.order_by(desc(GeneratedArtifactModel.created_at)).limit(max(1, min(limit, 500)))
            ).all()
            return [self._artifact_dict(row) for row in rows]


suite_store = SuiteStore()
