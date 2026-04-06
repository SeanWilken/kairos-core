from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import v1_router
from app.core.errors import http_exception_handler
from app.core.middleware import CorrelationIdMiddleware

app = FastAPI(
    title="Kairos Core Backend",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(CorrelationIdMiddleware)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.include_router(v1_router)
