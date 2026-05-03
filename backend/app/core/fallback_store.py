from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import FallbackApprovalRequestModel


def _dt_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


class FallbackStore:
    APPROVAL_TTL_SECONDS = 900

    def _to_dict(self, model: FallbackApprovalRequestModel) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        try:
            loaded = json.loads(model.metadata_json)
            if isinstance(loaded, dict):
                metadata = loaded
        except Exception:
            metadata = {}
        return {
            "request_id": model.request_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "room_id": model.room_id,
            "orchestration_run_id": model.orchestration_run_id,
            "persona_id": model.persona_id,
            "source_provider_id": model.source_provider_id,
            "source_model_id": model.source_model_id,
            "fallback_provider_id": model.fallback_provider_id,
            "fallback_model_id": model.fallback_model_id,
            "trigger_reason": model.trigger_reason,
            "status": model.status,
            "created_by_user_id": model.created_by_user_id,
            "approved_by_user_id": model.approved_by_user_id,
            "rejected_by_user_id": model.rejected_by_user_id,
            "metadata": metadata,
            "created_at": _dt_iso(model.created_at),
            "resolved_at": _dt_iso(model.resolved_at),
        }

    def create_request(
        self,
        *,
        tenant_id: str,
        org_id: str,
        room_id: str,
        orchestration_run_id: str,
        persona_id: str,
        source_provider_id: str,
        source_model_id: str,
        fallback_provider_id: str,
        fallback_model_id: str,
        trigger_reason: str,
        created_by_user_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            existing = db.scalar(
                select(FallbackApprovalRequestModel)
                .where(FallbackApprovalRequestModel.tenant_id == tenant_id)
                .where(FallbackApprovalRequestModel.org_id == org_id)
                .where(FallbackApprovalRequestModel.room_id == room_id)
                .where(FallbackApprovalRequestModel.persona_id == persona_id)
                .where(FallbackApprovalRequestModel.source_provider_id == source_provider_id)
                .where(FallbackApprovalRequestModel.source_model_id == source_model_id)
                .where(FallbackApprovalRequestModel.fallback_provider_id == fallback_provider_id)
                .where(FallbackApprovalRequestModel.fallback_model_id == fallback_model_id)
                .where(FallbackApprovalRequestModel.trigger_reason == trigger_reason)
                .where(FallbackApprovalRequestModel.status == "pending")
                .order_by(desc(FallbackApprovalRequestModel.created_at))
            )
            if existing is not None:
                return self._to_dict(existing)
            model = FallbackApprovalRequestModel(
                request_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                room_id=room_id,
                orchestration_run_id=orchestration_run_id,
                persona_id=persona_id,
                source_provider_id=source_provider_id,
                source_model_id=source_model_id,
                fallback_provider_id=fallback_provider_id,
                fallback_model_id=fallback_model_id,
                trigger_reason=trigger_reason,
                status="pending",
                created_by_user_id=created_by_user_id,
                approved_by_user_id=None,
                rejected_by_user_id=None,
                metadata_json=json.dumps(metadata or {}),
                created_at=datetime.now(timezone.utc),
                resolved_at=None,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_dict(model)

    def consume_approved_request(
        self,
        *,
        tenant_id: str,
        org_id: str,
        room_id: str,
        persona_id: str,
        source_provider_id: str,
        source_model_id: str,
        fallback_provider_id: str,
        fallback_model_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            rows = db.scalars(
                select(FallbackApprovalRequestModel)
                .where(FallbackApprovalRequestModel.tenant_id == tenant_id)
                .where(FallbackApprovalRequestModel.org_id == org_id)
                .where(FallbackApprovalRequestModel.room_id == room_id)
                .where(FallbackApprovalRequestModel.persona_id == persona_id)
                .where(FallbackApprovalRequestModel.source_provider_id == source_provider_id)
                .where(FallbackApprovalRequestModel.source_model_id == source_model_id)
                .where(FallbackApprovalRequestModel.fallback_provider_id == fallback_provider_id)
                .where(FallbackApprovalRequestModel.fallback_model_id == fallback_model_id)
                .where(FallbackApprovalRequestModel.status == "approved")
                .order_by(desc(FallbackApprovalRequestModel.resolved_at), desc(FallbackApprovalRequestModel.created_at))
            ).all()
            now = datetime.now(timezone.utc)
            for model in rows:
                resolved_at = model.resolved_at or model.created_at
                if resolved_at.tzinfo is None:
                    resolved_at = resolved_at.replace(tzinfo=timezone.utc)
                if resolved_at + timedelta(seconds=self.APPROVAL_TTL_SECONDS) < now:
                    model.status = "expired"
                    db.add(model)
                    continue
                model.status = "consumed"
                db.add(model)
                db.commit()
                db.refresh(model)
                return self._to_dict(model)
            db.commit()
            return None

    def list_requests(self, *, tenant_id: str, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(FallbackApprovalRequestModel).where(FallbackApprovalRequestModel.tenant_id == tenant_id)
            if status:
                stmt = stmt.where(FallbackApprovalRequestModel.status == status)
            rows = db.scalars(stmt.order_by(desc(FallbackApprovalRequestModel.created_at)).limit(limit)).all()
            return [self._to_dict(item) for item in rows]

    def resolve_request(self, *, tenant_id: str, request_id: str, decision: str, resolved_by_user_id: str) -> dict[str, Any] | None:
        if decision not in {"approve", "reject"}:
            return None
        with SessionLocal() as db:
            model = db.scalar(
                select(FallbackApprovalRequestModel).where(
                    FallbackApprovalRequestModel.tenant_id == tenant_id,
                    FallbackApprovalRequestModel.request_id == request_id,
                )
            )
            if model is None:
                return None
            if model.status != "pending":
                return self._to_dict(model)
            now = datetime.now(timezone.utc)
            if decision == "approve":
                model.status = "approved"
                model.approved_by_user_id = resolved_by_user_id
            else:
                model.status = "rejected"
                model.rejected_by_user_id = resolved_by_user_id
            model.resolved_at = now
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_dict(model)


fallback_store = FallbackStore()
