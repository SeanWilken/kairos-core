from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select, update

from app.core.db import SessionLocal
from app.core.db_models import ResumeAdapterPolicyModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class ResumeAdapterPolicyStore:
    def _to_dict(self, model: ResumeAdapterPolicyModel) -> dict[str, Any]:
        config: dict[str, Any] = {}
        try:
            loaded = json.loads(model.config_json)
            if isinstance(loaded, dict):
                config = loaded
        except Exception:
            config = {}
        return {
            "policy_id": model.policy_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "name": model.name,
            "version": model.version,
            "status": model.status,
            "config": config,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "rolled_back_from_policy_id": model.rolled_back_from_policy_id,
        }

    def list_policies(self, *, tenant_id: str, org_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(ResumeAdapterPolicyModel)
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .order_by(desc(ResumeAdapterPolicyModel.created_at))
            ).all()
            return [self._to_dict(row) for row in rows]

    def create_policy(
        self,
        *,
        tenant_id: str,
        org_id: str,
        name: str,
        config: dict[str, Any],
        created_by_user_id: str,
        status: str = "draft",
        rolled_back_from_policy_id: str = "",
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            latest_version = db.scalar(
                select(func.max(ResumeAdapterPolicyModel.version))
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.name == name)
            )
            version = int(latest_version or 0) + 1
            row = ResumeAdapterPolicyModel(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=name,
                version=version,
                status=status,
                config_json=json.dumps(config or {}),
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
                rolled_back_from_policy_id=rolled_back_from_policy_id,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)

    def activate_policy(self, *, tenant_id: str, org_id: str, policy_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            target = db.scalar(
                select(ResumeAdapterPolicyModel)
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.policy_id == policy_id)
            )
            if target is None:
                return None

            db.execute(
                update(ResumeAdapterPolicyModel)
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.name == target.name)
                .values(status="draft")
            )
            target.status = "active"
            db.add(target)
            db.commit()
            db.refresh(target)
            return self._to_dict(target)

    def get_active_policy(self, *, tenant_id: str, org_id: str, name: str = "default") -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(ResumeAdapterPolicyModel)
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.name == name)
                .where(ResumeAdapterPolicyModel.status == "active")
                .order_by(desc(ResumeAdapterPolicyModel.created_at))
            )
            if row is None:
                return None
            return self._to_dict(row)

    def rollback_to_policy(
        self,
        *,
        tenant_id: str,
        org_id: str,
        policy_id: str,
        created_by_user_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            source = db.scalar(
                select(ResumeAdapterPolicyModel)
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.policy_id == policy_id)
            )
            if source is None:
                return None
            config = {}
            try:
                loaded = json.loads(source.config_json)
                if isinstance(loaded, dict):
                    config = loaded
            except Exception:
                config = {}
            latest_version = db.scalar(
                select(func.max(ResumeAdapterPolicyModel.version))
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.name == source.name)
            )
            row = ResumeAdapterPolicyModel(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=source.name,
                version=int(latest_version or 0) + 1,
                status="active",
                config_json=json.dumps(config),
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
                rolled_back_from_policy_id=source.policy_id,
            )
            db.execute(
                update(ResumeAdapterPolicyModel)
                .where(ResumeAdapterPolicyModel.tenant_id == tenant_id)
                .where(ResumeAdapterPolicyModel.org_id == org_id)
                .where(ResumeAdapterPolicyModel.name == source.name)
                .values(status="draft")
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)


resume_adapter_policy_store = ResumeAdapterPolicyStore()
