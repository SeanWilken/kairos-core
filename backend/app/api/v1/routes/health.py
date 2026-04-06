from fastapi import APIRouter, Request

from app.core.response import ok_response

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(request: Request) -> dict:
    return ok_response(request, data={"status": "ok"})
