from fastapi import HTTPException, Request
from uuid import uuid4

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
    # we need DB tables for tenants and orgs before we can validate these, but for now just require that they are present in the headers?
    if not request.state.tenant_id:
        raise HTTPException(
            status_code=403, 
            detail={
                "message": "Tenant context is required.",
                "details": {
                    "reason_code": "TENANT_CONTEXT_MISSING"
                }
            }
        )
    if not request.state.org_id:
        raise HTTPException(
            status_code=403, 
            detail={
                "message": "Organization context is required.",
                "details": {
                    "reason_code": "ORG_CONTEXT_MISSING"
                }
            }
        )