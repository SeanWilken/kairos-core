from __future__ import annotations

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.tenant_store import tenant_store


def validate_tenant_scope(tenant_id: str) -> None:
    settings = get_settings()
    if not tenant_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Tenant context is required.",
                "details": {"reason_code": "TENANT_CONTEXT_MISSING"},
            },
        )

    if settings.single_tenant_mode:
        if settings.install_tenant_id and tenant_id != settings.install_tenant_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Tenant is outside install scope.",
                    "details": {
                        "reason_code": "TENANT_SCOPE_FORBIDDEN",
                        "install_tenant_id": settings.install_tenant_id,
                    },
                },
            )

        tenants = tenant_store.list_tenants()
        if tenants and all(row["tenant_id"] != tenant_id for row in tenants):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Tenant is outside install scope.",
                    "details": {
                        "reason_code": "TENANT_SCOPE_FORBIDDEN",
                        "install_tenant_id": tenants[0]["tenant_id"],
                    },
                },
            )


def require_existing_tenant(tenant_id: str) -> None:
    tenant = tenant_store.get_tenant(tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Tenant not found.",
                "details": {"reason_code": "TENANT_NOT_FOUND"},
            },
        )
