from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    service: str
    version: str
    spec_version: str
    environment: str
    timestamp: str
    correlation_id: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Envelope(BaseModel, Generic[T]):
    meta: Meta
    data: T | None = None
    error: ErrorBody | None = None
