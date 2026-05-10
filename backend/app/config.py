"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM provider
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")

    # Search
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")

    # DB / cache
    database_url: str = Field(
        default="postgresql+asyncpg://synapse:synapse@localhost:5432/synapse",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")
    # Set False only for local/dev HTTP. Prod must serve over HTTPS so the
    # auth cookie is never sent in cleartext.
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")

    # Server
    app_env: Literal["development", "test", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    log_format: Literal["auto", "json", "console"] = Field(
        default="auto",
        alias="LOG_FORMAT",
    )
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @field_validator("openrouter_api_key")
    @classmethod
    def _reject_empty_openrouter_api_key(cls, v: str) -> str:
        if not v or not v.strip():
            msg = "OPENROUTER_API_KEY must be set to a non-empty value (check .env or environment)"
            raise ValueError(msg)
        return v

    @field_validator("exa_api_key")
    @classmethod
    def _reject_empty_exa_api_key(cls, v: str) -> str:
        if not v or not v.strip():
            msg = "EXA_API_KEY must be set to a non-empty value (check .env or environment)"
            raise ValueError(msg)
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _reject_empty_jwt_secret(cls, v: str) -> str:
        if not v or not v.strip():
            msg = "JWT_SECRET must be set to a non-empty value (check .env or environment)"
            raise ValueError(msg)
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Use in dependency injection."""
    # Pydantic-settings populates fields from environment variables at runtime.
    # mypy cannot see this, so we suppress the missing-argument check.
    return Settings()  # type: ignore[call-arg]
