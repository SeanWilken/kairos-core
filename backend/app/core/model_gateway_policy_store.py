from __future__ import annotations

import fnmatch
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select, update

from app.core.db import SessionLocal
from app.core.db_models import ModelGatewayPolicyModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class ModelGatewayPolicyStore:
    def _to_dict(self, model: ModelGatewayPolicyModel) -> dict[str, Any]:
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
                select(ModelGatewayPolicyModel)
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .order_by(desc(ModelGatewayPolicyModel.created_at))
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
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            latest_version = db.scalar(
                select(func.max(ModelGatewayPolicyModel.version))
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.name == name)
            )
            row = ModelGatewayPolicyModel(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=name,
                version=int(latest_version or 0) + 1,
                status="draft",
                config_json=json.dumps(config or {}),
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
                rolled_back_from_policy_id="",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)

    def activate_policy(self, *, tenant_id: str, org_id: str, policy_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            target = db.scalar(
                select(ModelGatewayPolicyModel)
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.policy_id == policy_id)
            )
            if target is None:
                return None
            db.execute(
                update(ModelGatewayPolicyModel)
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.name == target.name)
                .values(status="draft")
            )
            target.status = "active"
            db.add(target)
            db.commit()
            db.refresh(target)
            return self._to_dict(target)

    def rollback_to_policy(self, *, tenant_id: str, org_id: str, policy_id: str, created_by_user_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            source = db.scalar(
                select(ModelGatewayPolicyModel)
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.policy_id == policy_id)
            )
            if source is None:
                return None
            latest_version = db.scalar(
                select(func.max(ModelGatewayPolicyModel.version))
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.name == source.name)
            )
            db.execute(
                update(ModelGatewayPolicyModel)
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.name == source.name)
                .values(status="draft")
            )
            row = ModelGatewayPolicyModel(
                policy_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=source.name,
                version=int(latest_version or 0) + 1,
                status="active",
                config_json=source.config_json,
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
                rolled_back_from_policy_id=source.policy_id,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)

    def resolve_runtime_policy(
        self,
        *,
        tenant_id: str,
        org_id: str,
        provider_id: str,
        model_id: str | None,
        default_timeout: float,
        default_retries: int,
    ) -> tuple[float, int]:
        with SessionLocal() as db:
            row = db.scalar(
                select(ModelGatewayPolicyModel)
                .where(ModelGatewayPolicyModel.tenant_id == tenant_id)
                .where(ModelGatewayPolicyModel.org_id == org_id)
                .where(ModelGatewayPolicyModel.name == "default")
                .where(ModelGatewayPolicyModel.status == "active")
                .order_by(desc(ModelGatewayPolicyModel.created_at))
            )
            if row is None:
                return default_timeout, default_retries
            try:
                config = json.loads(row.config_json)
            except Exception:
                config = {}
            if not isinstance(config, dict):
                return default_timeout, default_retries
            rules = config.get("provider_rules", []) if isinstance(config.get("provider_rules"), list) else []
            timeout = default_timeout
            retries = default_retries
            model_value = str(model_id or "").strip()
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                rule_provider = str(rule.get("provider_id", "")).strip().lower()
                if rule_provider and rule_provider != provider_id:
                    continue
                pattern = str(rule.get("model_pattern", "")).strip()
                if pattern and model_value and not fnmatch.fnmatch(model_value, pattern):
                    continue
                try:
                    timeout = float(rule.get("timeout_seconds", timeout))
                except Exception:
                    pass
                try:
                    retries = int(rule.get("retries", retries))
                except Exception:
                    pass
                break
            return timeout, retries


model_gateway_policy_store = ModelGatewayPolicyStore()
