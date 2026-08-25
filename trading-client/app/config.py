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
    DEFAULT_SYMBOLS: str = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,AVAXUSDT,LTCUSDT,TRXUSDT,LINKUSDT,DOTUSDT,MATICUSDT,ATOMUSDT,NEARUSDT,ARBUSDT,OPUSDT,APTUSDT,FILUSDT,INJUSDT,SUIUSDT,SEIUSDT,TIAUSDT,RNDRUSDT,FETUSDT,PEPEUSDT,SHIBUSDT,WIFUSDT,FLOKIUSDT,BONKUSDT,JUPUSDT,PYTHUSDT,STRTUSDT,WLDUSDT,ORDIUSDT,TONUSDT"
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
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GEMINI_API_KEY: str | None = None
    AI_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"
    OMNIROUTE_URL: str = "http://localhost:20128/v1"
    OMNIROUTE_API_KEY: str | None = None
    OMNIROUTE_MODEL: str = "auto"
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
    ENABLE_MULTI_BROKER: bool = True
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
    # Default broker for public market data endpoints (when no user/broker context)
    DEFAULT_BROKER_ID: str = "binance"
    # External market data API URLs (global intelligence, not broker-specific)
    FEAR_GREED_API_URL: str = "https://api.alternative.me/fng/"
    COINGECKO_API_URL: str = "https://api.coingecko.com/api/v3"
    MACRO_CALENDAR_URL: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    # Public market data fallback (used when no broker is connected)
    PUBLIC_MARKET_DATA_URL: str = "https://api.binance.com"
    # Risk engine parameters
    TRAILING_STOP_PCT: float = Field(default=2.0, gt=0.0, le=50.0)
    BREAKEVEN_THRESHOLD_PCT: float = Field(default=2.0, gt=0.0, le=50.0)
    # Profile risk limits (SL/TP ranges, min confidence, max positions per risk profile)
    CONSERVATIVE_SL_RANGE: str = "2.0,3.0"
    CONSERVATIVE_TP_RANGE: str = "4.0,8.0"
    CONSERVATIVE_MIN_CONFIDENCE: float = Field(default=0.7, ge=0.0, le=1.0)
    MODERATE_SL_RANGE: str = "3.0,4.0"
    MODERATE_TP_RANGE: str = "6.0,10.0"
    MODERATE_MIN_CONFIDENCE: float = Field(default=0.6, ge=0.0, le=1.0)
    AGGRESSIVE_SL_RANGE: str = "4.0,5.0"
    AGGRESSIVE_TP_RANGE: str = "8.0,15.0"
    AGGRESSIVE_MIN_CONFIDENCE: float = Field(default=0.5, ge=0.0, le=1.0)
    MAX_POSITIONS_PER_PROFILE: int = Field(default=999, ge=1)
    # LLM models that benefit from few-shot examples
    LIGHTWEIGHT_MODELS: str = "llama-3.1-8b-instant,llama3.2:3b,qwen2.5:7b,qwen2.5:14b,gemini-flash-lite-latest,gpt-4o-mini"
    # Premium LLM provider defaults (model and base_url per provider)
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_DEFAULT_BASE_URL: str = "https://api.openai.com/v1"
    DEEPSEEK_DEFAULT_MODEL: str = "deepseek-chat"
    DEEPSEEK_DEFAULT_BASE_URL: str = "https://api.deepseek.com/v1"
    MISTRAL_DEFAULT_MODEL: str = "mistral-small-latest"
    MISTRAL_DEFAULT_BASE_URL: str = "https://api.mistral.ai/v1"
    TOGETHER_DEFAULT_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    TOGETHER_DEFAULT_BASE_URL: str = "https://api.together.xyz/v1"
    PERPLEXITY_DEFAULT_MODEL: str = "llama-3.1-sonar-small-128k-online"
    PERPLEXITY_DEFAULT_BASE_URL: str = "https://api.perplexity.ai"
    GROK_DEFAULT_MODEL: str = "grok-beta"
    GROK_DEFAULT_BASE_URL: str = "https://api.x.ai/v1"
    # AI prompts directory (externalized prompt files)
    AI_PROMPTS_DIR: str = "app/ai/prompts"
    # Position reconciler interval (seconds between reconciliation cycles)
    RECONCILE_INTERVAL: int = Field(default=60, ge=10, le=3600)

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
        for key in (
            "BROKER_API_KEY", "BROKER_API_SECRET",
            "GROQ_API_KEY", "GEMINI_API_KEY",
            "ENCRYPTION_KEY",
            "WHATSAPP_ACCESS_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "REMOTE_AI_TOKEN",
            "OMNIROUTE_API_KEY",
        ):
            if safe.get(key):
                safe[key] = "***REDACTED***"
        for key, value in safe.items():
            if isinstance(value, _Decimal):
                safe[key] = str(value)
        return safe

    def get_profile_risk_limits(self) -> dict[str, dict[str, Any]]:
        """Build PROFILE_RISK_LIMITS dict from configurable settings."""
        def _parse_range(s: str) -> tuple[float, float]:
            parts = [float(x.strip()) for x in s.split(",")]
            return (parts[0], parts[1])
        max_pos = self.MAX_POSITIONS_PER_PROFILE
        return {
            "conservative": {"sl_range": _parse_range(self.CONSERVATIVE_SL_RANGE), "tp_range": _parse_range(self.CONSERVATIVE_TP_RANGE), "min_confidence": self.CONSERVATIVE_MIN_CONFIDENCE, "max_positions": max_pos},
            "moderate":     {"sl_range": _parse_range(self.MODERATE_SL_RANGE), "tp_range": _parse_range(self.MODERATE_TP_RANGE), "min_confidence": self.MODERATE_MIN_CONFIDENCE, "max_positions": max_pos},
            "aggressive":   {"sl_range": _parse_range(self.AGGRESSIVE_SL_RANGE), "tp_range": _parse_range(self.AGGRESSIVE_TP_RANGE), "min_confidence": self.AGGRESSIVE_MIN_CONFIDENCE, "max_positions": max_pos},
        }

    def get_lightweight_models(self) -> frozenset[str]:
        """Build LIGHTWEIGHT_MODELS frozenset from configurable setting."""
        return frozenset(m.strip() for m in self.LIGHTWEIGHT_MODELS.split(",") if m.strip())

    def get_provider_defaults(self) -> dict[str, dict]:
        """Build PROVIDER_DEFAULTS dict from configurable settings."""
        return {
            "openai": {"model": self.OPENAI_DEFAULT_MODEL, "base_url": self.OPENAI_DEFAULT_BASE_URL},
            "deepseek": {"model": self.DEEPSEEK_DEFAULT_MODEL, "base_url": self.DEEPSEEK_DEFAULT_BASE_URL},
            "mistral": {"model": self.MISTRAL_DEFAULT_MODEL, "base_url": self.MISTRAL_DEFAULT_BASE_URL},
            "together": {"model": self.TOGETHER_DEFAULT_MODEL, "base_url": self.TOGETHER_DEFAULT_BASE_URL},
            "perplexity": {"model": self.PERPLEXITY_DEFAULT_MODEL, "base_url": self.PERPLEXITY_DEFAULT_BASE_URL},
            "grok": {"model": self.GROK_DEFAULT_MODEL, "base_url": self.GROK_DEFAULT_BASE_URL},
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
