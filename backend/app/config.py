"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    jwt_secret: str = Field(default="", alias="JWT_SECRET")

    # Server
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Use in dependency injection."""
    return Settings()
