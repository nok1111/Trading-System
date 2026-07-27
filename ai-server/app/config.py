"""AI Server configuration — service-to-service HMAC, LLM providers, cache."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Alvora AI Server (cloud)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Service-to-service HMAC
    HMAC_SECRET: str = "change-me-in-production"
    HMAC_TIMESTAMP_WINDOW_SECONDS: int = 300  # 5 min

    # Auth Server URL for JWT validation
    AUTH_SERVER_URL: str = "http://localhost:8000"

    # LLM Providers (same as trading-client)
    AI_PROVIDER: str = "groq"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL_ECONOMIC: str = "llama-3.1-8b-instant"
    GROQ_MODEL_MEDIUM: str = "llama-3.3-70b-versatile"
    GROQ_MODEL_ADVANCED: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Cache
    CACHE_TTL_SECONDS: int = 60

    # CORS
    CORS_ORIGINS: str = "*"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=30, ge=1)

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
