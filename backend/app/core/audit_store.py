from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import AuditEventModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class AuditStore:
    def record_event(
        self,
        *,
        tenant_id: str,
        actor_type: str,
        actor_id: str,
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        room_id: str = "",
        orchestration_run_id: str = "",
        decision: str = "allowed",
        reason_code: str = "",
        policy_version: str = "v1",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            row = AuditEventModel(
                audit_event_id=str(uuid4()),
                tenant_id=tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                room_id=room_id,
                orchestration_run_id=orchestration_run_id,
                decision=decision,
                reason_code=reason_code,
                policy_version=policy_version,
                metadata_json=json.dumps(metadata or {}),
                created_at=now,
            )
            db.add(row)
            db.commit()
            return {
                "audit_event_id": row.audit_event_id,
                "tenant_id": row.tenant_id,
                "action": row.action,
                "decision": row.decision,
                "reason_code": row.reason_code,
                "created_at": _dt_iso(row.created_at),
            }

    def list_events(
        self,
        *,
        tenant_id: str,
        room_id: str | None = None,
        orchestration_run_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(AuditEventModel).where(AuditEventModel.tenant_id == tenant_id)
            if room_id:
                stmt = stmt.where(AuditEventModel.room_id == room_id)
            if orchestration_run_id:
                stmt = stmt.where(AuditEventModel.orchestration_run_id == orchestration_run_id)
            rows = db.scalars(stmt.order_by(desc(AuditEventModel.created_at)).limit(limit)).all()

            items: list[dict[str, Any]] = []
            for row in rows:
                metadata: dict[str, Any] = {}
                try:
                    loaded = json.loads(row.metadata_json)
                    if isinstance(loaded, dict):
                        metadata = loaded
                except Exception:
                    metadata = {}
                items.append(
                    {
                        "audit_event_id": row.audit_event_id,
                        "tenant_id": row.tenant_id,
                        "actor_type": row.actor_type,
                        "actor_id": row.actor_id,
                        "action": row.action,
                        "resource_type": row.resource_type,
                        "resource_id": row.resource_id,
                        "room_id": row.room_id,
                        "orchestration_run_id": row.orchestration_run_id,
                        "decision": row.decision,
                        "reason_code": row.reason_code,
                        "policy_version": row.policy_version,
                        "metadata": metadata,
                        "created_at": _dt_iso(row.created_at),
                    }
                )
            return items


audit_store = AuditStore()
