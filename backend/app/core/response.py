from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.core.schemas import Envelope, ErrorBody, Meta


def build_meta(request: Request) -> Meta:
    settings = get_settings()
    return Meta(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        correlation_id=getattr(request.state, "correlation_id", "unknown"),
    )


def ok_response(request: Request, data: dict[str, Any]) -> dict[str, Any]:
    return Envelope(meta=build_meta(request), data=data, error=None).model_dump()


def error_response(
    request: Request,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return Envelope(
        meta=build_meta(request),
        data=None,
        error=ErrorBody(code=code, message=message, details=details or {}),
    ).model_dump()
