from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel


def _default_database_url() -> str:
    data_dir = Path.home() / ".kairos" / "kairos-core"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "onboarding.db"
    return f"sqlite+pysqlite:///{db_path.as_posix()}"


class Settings(BaseModel):
    app_name: str
    app_env: str
    app_version: str
    database_url: str
    cors_allowed_origins: list[str]


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

    return Settings(
        app_name=os.getenv("APP_NAME", "kairos-core-backend"),
        app_env=app_env,
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        database_url=(
            os.getenv("KAIROS_DATABASE_URL") or os.getenv("DATABASE_URL") or _default_database_url()
        ),
        cors_allowed_origins=cors_allowed_origins,
    )
