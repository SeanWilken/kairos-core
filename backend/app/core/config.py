from functools import lru_cache
import os

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "kairos-core-backend")
    app_env: str = os.getenv("APP_ENV", "local")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")


@lru_cache
def get_settings() -> Settings:
    return Settings()
