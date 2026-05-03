from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select

from app.core.audit_store import audit_store
from app.core.db import SessionLocal
from app.core.db_models import ConversationOrchestrationRunModel, EventOutboxModel


def _dt_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


class OrchestrationStore:
    def _to_run_dict(self, model: ConversationOrchestrationRunModel) -> dict[str, Any]:
        return {
            "run_id": model.run_id,
            "tenant_id": model.tenant_id,
            "room_id": model.room_id,
            "triggering_message_id": model.triggering_message_id,
            "parent_run_id": model.parent_run_id,
            "source_run_id": model.source_run_id,
            "created_by_user_id": model.created_by_user_id,
            "orchestration_type": model.orchestration_type,
            "mode": model.mode,
            "status": model.status,
            "client_message_id": model.client_message_id,
            "idempotency_key": model.idempotency_key,
            "failure_reason": model.failure_reason,
            "total_input_tokens": model.total_input_tokens,
            "total_output_tokens": model.total_output_tokens,
            "total_cost_estimate": model.total_cost_estimate,
            "created_at": _dt_iso(model.created_at),
            "started_at": _dt_iso(model.started_at),
            "completed_at": _dt_iso(model.completed_at),
            "failed_at": _dt_iso(model.failed_at),
        }

    def _next_outbox_sequence(self, *, db, tenant_id: str, room_id: str) -> int:
        current_max = db.scalar(
            select(func.max(EventOutboxModel.sequence)).where(
                EventOutboxModel.tenant_id == tenant_id,
                EventOutboxModel.room_id == room_id,
            )
        )
        return int(current_max or 0) + 1

    def get_run_by_idempotency(
        self,
        *,
        tenant_id: str,
        room_id: str,
        created_by_user_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        with SessionLocal() as db:
            model = db.scalar(
                select(ConversationOrchestrationRunModel)
                .where(
                    ConversationOrchestrationRunModel.tenant_id == tenant_id,
                    ConversationOrchestrationRunModel.room_id == room_id,
                    ConversationOrchestrationRunModel.created_by_user_id == created_by_user_id,
                    ConversationOrchestrationRunModel.idempotency_key == key,
                )
                .order_by(ConversationOrchestrationRunModel.created_at.desc())
            )
            return self._to_run_dict(model) if model else None

    def create_run(
        self,
        *,
        tenant_id: str,
        room_id: str,
        triggering_message_id: str | None,
        created_by_user_id: str | None,
        orchestration_type: str,
        mode: str,
        client_message_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            model = ConversationOrchestrationRunModel(
                run_id=str(uuid4()),
                tenant_id=tenant_id,
                room_id=room_id,
                triggering_message_id=triggering_message_id,
                parent_run_id=None,
                source_run_id=None,
                created_by_user_id=created_by_user_id,
                orchestration_type=orchestration_type,
                mode=mode,
                status="running",
                client_message_id=client_message_id,
                idempotency_key=idempotency_key,
                failure_reason="",
                total_input_tokens=0,
                total_output_tokens=0,
                total_cost_estimate=0.0,
                created_at=now,
                started_at=now,
                completed_at=None,
                failed_at=None,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            audit_store.record_event(
                tenant_id=model.tenant_id,
                actor_type="system",
                actor_id="orchestration_store",
                action="orchestration.run.completed",
                resource_type="orchestration_run",
                resource_id=model.run_id,
                room_id=model.room_id,
                orchestration_run_id=model.run_id,
                metadata={
                    "input_tokens": model.total_input_tokens,
                    "output_tokens": model.total_output_tokens,
                },
            )
            return self._to_run_dict(model)

    def complete_run(
        self,
        *,
        run_id: str,
        usage: dict[str, Any] | None = None,
        cost_estimate: float | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(ConversationOrchestrationRunModel).where(
                    ConversationOrchestrationRunModel.run_id == run_id,
                )
            )
            if model is None:
                return None
            usage_data = usage or {}
            model.total_input_tokens = int(usage_data.get("input_tokens", 0) or 0)
            model.total_output_tokens = int(usage_data.get("output_tokens", 0) or 0)
            model.total_cost_estimate = float(cost_estimate or 0.0)
            model.status = "completed"
            model.completed_at = datetime.now(timezone.utc)
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_run_dict(model)

    def fail_run(self, *, run_id: str, reason: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(ConversationOrchestrationRunModel).where(
                    ConversationOrchestrationRunModel.run_id == run_id,
                )
            )
            if model is None:
                return None
            model.status = "failed"
            model.failure_reason = str(reason or "unknown_error")
            model.failed_at = datetime.now(timezone.utc)
            db.add(model)
            db.commit()
            db.refresh(model)
            audit_store.record_event(
                tenant_id=model.tenant_id,
                actor_type="system",
                actor_id="orchestration_store",
                action="orchestration.run.failed",
                resource_type="orchestration_run",
                resource_id=model.run_id,
                room_id=model.room_id,
                orchestration_run_id=model.run_id,
                decision="denied",
                reason_code=model.failure_reason,
            )
            return self._to_run_dict(model)

    def add_outbox_event(
        self,
        *,
        tenant_id: str,
        room_id: str,
        orchestration_run_id: str | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            sequence = self._next_outbox_sequence(db=db, tenant_id=tenant_id, room_id=room_id)
            model = EventOutboxModel(
                outbox_event_id=str(uuid4()),
                tenant_id=tenant_id,
                room_id=room_id,
                orchestration_run_id=orchestration_run_id,
                sequence=sequence,
                event_type=event_type,
                payload_json=json.dumps(payload),
                created_at=datetime.now(timezone.utc),
                delivered_at=None,
            )
            db.add(model)
            db.commit()
            return {
                "event_id": model.outbox_event_id,
                "sequence": model.sequence,
                "event_type": model.event_type,
                "room_id": room_id,
                "tenant_id": tenant_id,
                "orchestration_run_id": orchestration_run_id,
            }


orchestration_store = OrchestrationStore()
