from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Async URL for FastAPI + SQLAlchemy (asyncpg)
    database_url: str = "postgresql+asyncpg://localhost/rlhf"

    # Sync URL for Alembic (psycopg). If empty, derived from database_url.
    database_url_sync: str = ""

    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    root_path: str = ""
    app_env: str = "dev"
    debug: bool = False
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    @field_validator("database_url")
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://") and "+asyncpg" not in v and "+psycopg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def sync_database_url(self) -> str:
        if self.database_url_sync:
            u = self.database_url_sync
            if u.startswith("postgresql://") and "+psycopg" not in u:
                return u.replace("postgresql://", "postgresql+psycopg://", 1)
            return u
        u = self.database_url
        return u.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
