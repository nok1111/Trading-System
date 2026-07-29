from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Trading Client configuration — local settings for trading + AI.

    All sensitive values (Binance keys, AI keys) are read from the local
    .env file and NEVER sent to the Auth Server.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    DATABASE_URL: str = "sqlite:///./trading.db"
    # Auth Server connection
    AUTH_SERVER_URL: str = "http://76.13.180.80:8000"
    # Broker
    BROKER_PROVIDER: Literal["mock", "paper", "alpaca", "ibkr", "binance"] = "mock"
    BINANCE_TESTNET: bool = False
    BROKER_API_KEY: str | None = None
    BROKER_API_SECRET: str | None = None
    # Trading mode
    TRADING_MODE: Literal["backtest", "paper", "live"] = "paper"
    LIVE_TRADING_ENABLED: bool = False
    DEFAULT_SYMBOLS: str = "BTCUSDT,ETHUSDT,SOLUSDT"
    MAX_POSITION_SIZE_PERCENT: float = Field(default=10.0, ge=0.0, le=100.0)
    MAX_RISK_PER_TRADE_PERCENT: float = Field(default=1.0, ge=0.0, le=100.0)
    MAX_DAILY_LOSS_PERCENT: float = Field(default=3.0, ge=0.0, le=100.0)
    MIN_CASH_RESERVE_PERCENT: float = Field(default=20.0, ge=0.0, le=100.0)
    MAX_OPEN_POSITIONS: int = Field(default=20, ge=1)
    MAX_HOLD_SYMBOLS: int = Field(default=8, ge=1)
    MAX_ACTIVE_SYMBOLS: int = Field(default=10, ge=1)
    HOLD_STALE_TICKS: int = Field(default=10, ge=1)
    DEFAULT_STOP_LOSS_PERCENT: float = Field(default=3.0, gt=0.0)
    DEFAULT_TAKE_PROFIT_PERCENT: float = Field(default=6.0, gt=0.0)
    DATA_TIMEFRAME: str = "5m"
    PAPER_TRADING_ENABLED: bool = False
    PAPER_TRADING_INTERVAL_SECONDS: int = Field(default=300, ge=5)
    PAPER_TRADING_LOOKBACK_DAYS: int = Field(default=60, ge=1)
    PAPER_TRADING_INITIAL_CASH: Decimal = Decimal("100000.00")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    JSON_LOGS: bool = False
    TIMEZONE: str = "America/Chicago"
    # WhatsApp
    WHATSAPP_PHONE_NUMBER_ID: str | None = None
    WHATSAPP_ACCESS_TOKEN: str | None = None
    WHATSAPP_TO_NUMBER: str | None = None
    # AI Provider
    AI_PROVIDER: Literal["groq", "ollama", "gemini"] = "groq"
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    AI_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"
    AI_INTERVAL_SECONDS: int = Field(default=30, ge=10)
    AI_AUTO_TRADE: bool = True
    AI_ALLOCATED_CAPITAL: float = 0.0
    # Encryption (for local SQLite encrypted keys if needed)
    ENCRYPTION_KEY: str = ""
    # Telegram bot
    TELEGRAM_BOT_TOKEN: str | None = None
    # Live trading safety
    LIVE_MAX_ORDER_USD: float = Field(default=500.0, gt=0.0)
    LIVE_DAILY_LOSS_LIMIT_USD: float = Field(default=100.0, gt=0.0)
    LIVE_KILL_SWITCH: bool = False
    LIVE_CONFIRMATION_REQUIRED: bool = True
    # Multi-broker feature flag
    ENABLE_MULTI_BROKER: bool = False
    # AI provider feature flags
    USE_REMOTE_AI: bool = False
    REMOTE_AI_URL: str | None = None
    REMOTE_AI_TOKEN: str | None = None
    REMOTE_AI_PERCENTAGE: int = Field(default=0, ge=0, le=100)
    ENABLE_AI_SHADOW_MODE: bool = False
    # Intelligence Platform (new architecture)
    USE_INTELLIGENCE_API: bool = False
    # Risk Engine feature flag
    ENABLE_AUTOMATIC_EXECUTION: bool = True

    @field_validator("DEFAULT_SYMBOLS")
    @classmethod
    def normalize_symbols(cls, value: str) -> str:
        symbols = [s.strip().upper() for s in value.split(",") if s.strip()]
        if not symbols:
            raise ValueError("DEFAULT_SYMBOLS debe contener al menos un símbolo")
        return ",".join(symbols)

    @model_validator(mode="after")
    def validate_live_mode(self) -> "Settings":
        if self.TRADING_MODE == "live" and not self.LIVE_TRADING_ENABLED:
            raise ValueError("TRADING_MODE='live' requiere LIVE_TRADING_ENABLED=true")
        return self

    @property
    def symbols_list(self) -> list[str]:
        return [s.strip() for s in self.DEFAULT_SYMBOLS.split(",") if s.strip()]

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)

    def now_local(self) -> datetime:
        return datetime.now(tz=self.tzinfo)

    def to_safe_dict(self) -> dict[str, Any]:
        """Retorna la configuración ocultando secretos."""
        from decimal import Decimal as _Decimal

        safe = self.model_dump()
        for key in ("BROKER_API_KEY", "BROKER_API_SECRET"):
            if safe.get(key):
                safe[key] = "***REDACTED***"
        for key, value in safe.items():
            if isinstance(value, _Decimal):
                safe[key] = str(value)
        return safe


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
