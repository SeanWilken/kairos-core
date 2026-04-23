from fastapi import HTTPException, Request
from uuid import uuid4

from app.core.config import get_settings

CORRELATION_ID_HEADER = "X-Correlation-ID"
TENANT_ID_HEADER = "X-Tenant-ID"
ORG_ID_HEADER = "X-Org-ID"


def get_tenant_id(request: Request) -> str | None:
    return request.headers.get(TENANT_ID_HEADER)


def get_org_id(request: Request) -> str | None:
    return request.headers.get(ORG_ID_HEADER)


def get_correlation_id(request: Request) -> str:
    correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())
    return correlation_id


def require_request_scope(request: Request) -> None:
    tenant_id = request.state.tenant_id
    org_id = request.state.org_id

    if tenant_id and org_id:
        return

    path = getattr(getattr(request, "url", None), "path", "")
    if get_settings().app_env == "local" and path and not path.startswith("/v1/protected"):
        request.state.tenant_id = tenant_id or "tenant-local"
        request.state.org_id = org_id or "org-local"
        return

    if not tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Tenant context is required.",
                "details": {"reason_code": "TENANT_CONTEXT_MISSING"},
            },
        )
    if not org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Organization context is required.",
                "details": {"reason_code": "ORG_CONTEXT_MISSING"},
            },
        )
