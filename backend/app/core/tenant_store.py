from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.db_models import TenantModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class TenantStore:
    def _to_dict(self, tenant: TenantModel) -> dict[str, Any]:
        return {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "status": tenant.status,
            "created_at": _dt_iso(tenant.created_at),
            "updated_at": _dt_iso(tenant.updated_at),
        }

    def create_tenant(self, *, tenant_id: str, name: str, status: str = "active") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            tenant = TenantModel(
                tenant_id=tenant_id,
                name=name,
                status=status,
                created_at=now,
                updated_at=now,
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            return self._to_dict(tenant)

    def get_tenant(self, *, tenant_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            tenant = db.scalar(select(TenantModel).where(TenantModel.tenant_id == tenant_id))
            if tenant is None:
                return None
            return self._to_dict(tenant)

    def list_tenants(self) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(select(TenantModel).order_by(TenantModel.created_at.asc())).all()
            return [self._to_dict(row) for row in rows]


tenant_store = TenantStore()
