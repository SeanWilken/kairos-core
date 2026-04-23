from fastapi import APIRouter, Request

from app.core.auth_context import require_authentication
from app.core.response import ok_response

router = APIRouter(tags=["protected"])


@router.get("/protected/ping")
def get_protected(request: Request) -> dict:
    context = require_authentication(request)
    return ok_response(
        request,
        data={
            "status": "ok",
            "tenant_id": context.tenant_id,
            "org_id": context.org_id,
            "user_id": context.user_id,
            "message": "Protected pong.",
        },
    )
