import os
from functools import lru_cache

from pydantic import field_validator, model_validator
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

    # Inference provider: "huggingface", "nvidia", or "custom"
    inference_provider: str = "huggingface"
    inference_enabled: bool = True
    inference_require_auth: bool = False
    inference_max_tokens: int = 1024
    inference_max_prompt_chars: int = 48000
    inference_timeout_seconds: float = 120.0

    # Hugging Face Inference Providers (OpenAI-compatible router)
    hf_api_token: str | None = None
    hf_router_base_url: str = "https://router.huggingface.co/v1"
    hf_default_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # NVIDIA NIM (OpenAI-compatible)
    nvidia_api_token: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_default_model: str = "nvidia/llama-3.3-nemotron-super-49b-v1"

    # Custom OpenAI-compatible provider
    custom_api_token: str | None = None
    custom_base_url: str = ""
    custom_default_model: str = ""

    @property
    def active_api_token(self) -> str | None:
        if self.inference_provider == "nvidia":
            return self.nvidia_api_token
        if self.inference_provider == "custom":
            return self.custom_api_token
        return self.hf_api_token

    @property
    def active_base_url(self) -> str:
        if self.inference_provider == "nvidia":
            return self.nvidia_base_url
        if self.inference_provider == "custom":
            return self.custom_base_url
        return self.hf_router_base_url

    @property
    def active_default_model(self) -> str:
        if self.inference_provider == "nvidia":
            return self.nvidia_default_model
        if self.inference_provider == "custom":
            return self.custom_default_model
        return self.hf_default_model

    @model_validator(mode="after")
    def resolve_token_env_aliases(self) -> "Settings":
        if not self.hf_api_token:
            self.hf_api_token = os.environ.get("HF_TOKEN") or os.environ.get(
                "HUGGINGFACE_HUB_TOKEN",
            )
        if not self.nvidia_api_token:
            self.nvidia_api_token = os.environ.get("NVIDIA_API_KEY") or os.environ.get(
                "NGC_API_KEY",
            )
        return self

    @model_validator(mode="after")
    def warn_default_jwt_secret(self) -> "Settings":
        if self.jwt_secret == "change-me-in-production":
            import logging

            logging.getLogger("app.config").warning(
                "JWT_SECRET is set to the default value. Set a strong secret in production!",
            )
        return self

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
