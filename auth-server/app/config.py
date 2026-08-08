"""Auth Server configuration — PostgreSQL, JWT, Binance Pay."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the Alvora Auth Server (cloud)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    DATABASE_URL: str = "postgresql+psycopg2://alvora:alvora@localhost:5432/alvora_auth"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Auth
    JWT_SECRET: str = Field(default="change-me-in-production", description="Must be overridden in production via env var")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # Binance Pay (merchant)
    BINANCE_PAY_API_KEY: str | None = None
    BINANCE_PAY_API_SECRET: str | None = None
    BINANCE_PAY_MERCHANT_ID: str | None = None

    # CORS — Trading Client origins
    CORS_ORIGINS: str = "http://localhost:1420,http://127.0.0.1:1420"

    # Service URLs for monitoring (used by admin panel)
    TRADING_CLIENT_URL: str = "http://localhost:8080"
    AI_SERVER_URL: str = "http://localhost:8001"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
