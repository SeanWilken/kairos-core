from fastapi import APIRouter, Request

from app.core.response import ok_response

from app.core.request_context import require_request_scope

router = APIRouter(tags=["protected"])

@router.get("/protected/ping")
def get_protected(request: Request) -> dict:
    require_request_scope(request)
    return ok_response(request, data={"status": "ok", "tenant_id": request.state.tenant_id, "org_id": request.state.org_id, "message": "Protected pong."})