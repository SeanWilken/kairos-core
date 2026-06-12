from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel


def _default_database_url() -> str:
    data_dir = Path.home() / ".myai" / "myai-core"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "onboarding.db"
    return f"sqlite+pysqlite:///{db_path.as_posix()}"


class Settings(BaseModel):
    app_name: str
    app_env: str
    app_version: str
    database_url: str
    cors_allowed_origins: list[str]
    jwt_secret: str
    jwt_access_token_ttl_minutes: int
    jwt_refresh_token_ttl_days: int
    single_tenant_mode: bool
    install_tenant_id: str


@lru_cache
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "local")
    cors_default = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:8080,"
        "http://127.0.0.1:8080,"
        "http://localhost:8081,"
        "http://127.0.0.1:8081,"
        "http://localhost:8082,"
        "http://127.0.0.1:8082,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
        if app_env == "local"
        else ""
    )
    raw_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", cors_default)
    cors_allowed_origins = [
        origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()
    ]

    single_tenant_mode = os.getenv("SINGLE_TENANT_MODE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return Settings(
        app_name=os.getenv("APP_NAME", "myai-core-backend"),
        app_env=app_env,
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        database_url=(
            os.getenv("MYAI_DATABASE_URL") or os.getenv("DATABASE_URL") or _default_database_url()
        ),
        cors_allowed_origins=cors_allowed_origins,
        jwt_secret=os.getenv("JWT_SECRET", "myai-local-dev-secret-change-me"),
        jwt_access_token_ttl_minutes=int(os.getenv("JWT_ACCESS_TTL_MINUTES", "15")),
        jwt_refresh_token_ttl_days=int(os.getenv("JWT_REFRESH_TTL_DAYS", "14")),
        single_tenant_mode=single_tenant_mode,
        install_tenant_id=os.getenv("INSTALL_TENANT_ID", ""),
    )
