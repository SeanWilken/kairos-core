from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import v1_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.errors import http_exception_handler
from app.core.middleware import CorrelationIdMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Kairos Core Backend",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
if get_settings().cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.include_router(v1_router)
