from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import DailySummaryModel


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


class DailySummaryStore:
    def _to_dict(self, row: DailySummaryModel) -> dict[str, Any]:
        return {
            "summary_id": row.summary_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "user_id": row.user_id,
            "date": row.summary_date.date().isoformat(),
            "highlights": json.loads(row.highlights_json),
            "sections": json.loads(row.sections_json),
            "summary": json.loads(row.stats_json),
            "metadata": json.loads(row.metadata_json),
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }

    def upsert_summary(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        summary_date: date,
        highlights: list[str],
        sections: dict[str, Any],
        stats: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        day = _day_start(summary_date)
        with SessionLocal() as db:
            row = db.scalar(
                select(DailySummaryModel).where(
                    DailySummaryModel.tenant_id == tenant_id,
                    DailySummaryModel.org_id == org_id,
                    DailySummaryModel.user_id == user_id,
                    DailySummaryModel.summary_date == day,
                )
            )
            if row is None:
                row = DailySummaryModel(
                    summary_id=str(uuid4()),
                    tenant_id=tenant_id,
                    org_id=org_id,
                    user_id=user_id,
                    summary_date=day,
                    created_at=now,
                    updated_at=now,
                )
            row.highlights_json = json.dumps(highlights)
            row.sections_json = json.dumps(sections)
            row.stats_json = json.dumps(stats)
            row.metadata_json = json.dumps(metadata or {})
            row.updated_at = now
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_dict(row)

    def list_summaries(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(DailySummaryModel).where(
                DailySummaryModel.tenant_id == tenant_id,
                DailySummaryModel.org_id == org_id,
                DailySummaryModel.user_id == user_id,
            )
            if start_date is not None:
                stmt = stmt.where(DailySummaryModel.summary_date >= _day_start(start_date))
            if end_date is not None:
                stmt = stmt.where(DailySummaryModel.summary_date <= _day_start(end_date))
            rows = db.scalars(stmt.order_by(desc(DailySummaryModel.summary_date)).limit(limit)).all()
            return [self._to_dict(row) for row in rows]

    def get_summary_for_date(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        summary_date: date,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DailySummaryModel).where(
                    DailySummaryModel.tenant_id == tenant_id,
                    DailySummaryModel.org_id == org_id,
                    DailySummaryModel.user_id == user_id,
                    DailySummaryModel.summary_date == _day_start(summary_date),
                )
            )
            return self._to_dict(row) if row else None


daily_summary_store = DailySummaryStore()
