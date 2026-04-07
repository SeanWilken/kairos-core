from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import error_response

def map_http_exception_code(status_code: int) -> str:
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 403:
        return "ACCESS_DENIED"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code == 500:
        return "INTERNAL_SERVER_ERROR"
    return "HTTP_ERROR"

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, str):
        message = exc.detail
        details = {}
    elif isinstance(exc.detail, dict):
        message = exc.detail.get("message", "Request failed")
        details = exc.detail.get("details", {})
    else:
        message = "Request failed."
        details = {}
    body = error_response(
        request=request,
        code=map_http_exception_code(exc.status_code),
        message=message,
        details=details,
    )
    return JSONResponse(status_code=exc.status_code, content=body)
