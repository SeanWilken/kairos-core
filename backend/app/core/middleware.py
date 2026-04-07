from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.request_context import CORRELATION_ID_HEADER, get_correlation_id, get_org_id, get_tenant_id

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # extract the headers to check
        correlation_id = get_correlation_id(request)
        tenant_id = get_tenant_id(request)
        org_id = get_org_id(request)

        request.state.correlation_id = correlation_id
        request.state.tenant_id = tenant_id
        request.state.org_id = org_id
        
        response = await call_next(request)

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
