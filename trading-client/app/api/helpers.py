"""Shared helper functions across API routers."""

from fastapi import HTTPException

from app.brokers.models import BrokerCredentials
from app.config import get_settings
from app.database.session import SessionLocal
from app.services.crypto import decrypt


def resolve_binancekeys(current_user=None) -> tuple[str, str] | None:
    """Resolve Binance API keys from broker_accounts table for the current user.

    No .env fallback, no test accounts. The user connects their broker
    through the Connections page and those keys are used.
    """
    user_id = None
    if current_user:
        user_id = getattr(current_user, "id", None)
    if user_id is None:
        return None
    try:
        session = SessionLocal()
        from app.database.models.broker_account import BrokerAccount as BA
        query = session.query(BA).filter_by(broker_id="binance", user_id=user_id)
        row = query.first()
        if row and row.api_key_enc:
            key = decrypt(row.api_key_enc)
            secret = decrypt(row.api_secret_enc)
            if key and secret:
                session.close()
                return (key, secret)
        session.close()
    except Exception:
        pass
    return None


def resolve_broker_credentials(
    broker_id: str = "binance",
    current_user=None,
) -> BrokerCredentials | None:
    """Resolve broker credentials from broker_accounts table for the current user.

    Broker-agnostic: works with any broker_id (binance, coinbase, okx, etc.).
    No .env fallback, no test accounts. The user connects their broker
    through the Connections page and those keys are used.
    """
    user_id = None
    if current_user:
        user_id = getattr(current_user, "id", None)
    if user_id is None:
        return None
    try:
        session = SessionLocal()
        from app.database.models.broker_account import BrokerAccount as BA
        query = session.query(BA).filter_by(broker_id=broker_id, user_id=user_id)
        row = query.first()
        session.close()
        if row and row.api_key_enc:
            return BrokerCredentials(
                broker_id=broker_id,
                api_key=decrypt(row.api_key_enc),
                api_secret=decrypt(row.api_secret_enc),
                passphrase=decrypt(row.passphrase_enc) if row.passphrase_enc else None,
                testnet=row.environment in ("testnet", "demo", "sandbox"),
            )
    except Exception:
        pass
    return None


def build_strategy(name: str, settings):
    """Construye una estrategia por nombre."""
    if name == "ml":
        from pathlib import Path

        from app.ml import MLPredictor
        model_path = "models/BTCUSDT_ml_model.json"
        if not Path(model_path).exists():
            raise HTTPException(status_code=400, detail="No hay modelo ML entrenado. Entrena uno primero.")
        predictor = MLPredictor.load(model_path)
        from app.ml.strategy import MLStrategy, MLStrategyConfig
        return MLStrategy(model=predictor.model, feature_engineer=predictor.feature_engineer, config=MLStrategyConfig())
    if name in ("mean_reversion", "MeanReversionStrategy"):
        from app.strategies import MeanReversionConfig, MeanReversionStrategy
        return MeanReversionStrategy(MeanReversionConfig())
    if name in ("breakout", "BreakoutStrategy"):
        from app.strategies import BreakoutConfig, BreakoutStrategy
        return BreakoutStrategy(BreakoutConfig())
    if name in ("grid", "GridStrategy"):
        from app.strategies import GridConfig, GridStrategy
        return GridStrategy(GridConfig())
    if name in ("macd_momentum", "MACDMomentumStrategy"):
        from app.strategies import MACDMomentumConfig, MACDMomentumStrategy
        return MACDMomentumStrategy(MACDMomentumConfig())
    if name in ("bollinger_squeeze", "BollingerSqueezeStrategy"):
        from app.strategies import BollingerSqueezeConfig, BollingerSqueezeStrategy
        return BollingerSqueezeStrategy(BollingerSqueezeConfig())
    if name in ("supertrend", "SupertrendStrategy"):
        from app.strategies import SupertrendConfig, SupertrendStrategy
        return SupertrendStrategy(SupertrendConfig())
    if name in ("rsi_divergence", "RSIDivergenceStrategy"):
        from app.strategies import RSIDivergenceConfig, RSIDivergenceStrategy
        return RSIDivergenceStrategy(RSIDivergenceConfig())
    # default: trend
    from app.strategies import TrendMomentumConfig, TrendMomentumStrategy
    return TrendMomentumStrategy(TrendMomentumConfig())


def get_shared_broker(binance_keys: tuple[str, str] | None = None):
    """Obtiene el broker compartido del paper trading o usa/crea uno persistente para AI agent.

    En modo live con BROKER_PROVIDER=binance y API keys configuradas,
    retorna un BinanceBroker real que ejecuta órdenes en Binance.
    Si se pasan binance_keys, se usan esas keys en lugar de las del .env.
    """
    import app.api.state as state

    schedulers = state.paper_trading_state.get("schedulers", [])
    if schedulers:
        return schedulers[0].broker

    # Thread-safe check-and-set for shared broker
    with state.ai_broker_lock:
        if state.ai_shared_broker is not None and state.ai_shared_broker_keys == binance_keys:
            return state.ai_shared_broker

    # Crear broker usando la factory (MockBroker o BinanceBroker según config)
    from app.database.models.position import Position as PosModel
    from app.factories import create_broker

    settings = get_settings()

    if binance_keys:
        # Override settings with user keys
        override = settings.model_copy(update={"BROKER_API_KEY": binance_keys[0], "BROKER_API_SECRET": binance_keys[1]})
        broker = create_broker(override)
    else:
        broker = create_broker(settings)

    # Si es MockBroker, sincronizar desde BD para mantener estado
    if hasattr(broker, "sync_from_db"):
        session = SessionLocal()
        try:
            open_pos = session.query(PosModel).filter_by(status="open").all()
            if open_pos:
                broker.sync_from_db(open_pos, settings.PAPER_TRADING_INITIAL_CASH)
        finally:
            session.close()

    with state.ai_broker_lock:
        state.ai_shared_broker = broker
        state.ai_shared_broker_keys = binance_keys
    return broker


def create_ai_snapshot(broker) -> None:
    """Crea un snapshot de cuenta para que el tab Resumen muestre datos del AI Agent."""
    from datetime import UTC, datetime

    from app.database.models.account_snapshot import AccountSnapshot

    account = broker.get_account()
    session = SessionLocal()
    try:
        snapshot = AccountSnapshot(
            broker_id=broker.name,
            timestamp=datetime.now(tz=UTC),
            cash=account.cash,
            equity=account.equity,
            buying_power=account.buying_power,
            margin_used=account.margin_used,
            daily_pnl=account.daily_pnl,
            total_pnl=account.total_pnl,
            open_positions_count=account.open_positions_count,
            strategy_run_id=None,
        )
        session.add(snapshot)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def get_or_create_agent():
    """Obtiene o crea el AI agent singleton."""
    import app.api.state as state
    from app.ai.agent import AITradingAgent

    with state.ai_lock:
        if state.ai_agent is None:
            settings = get_settings()

            # Defaults from .env
            provider = getattr(settings, "AI_PROVIDER", "groq")
            groq_api_key = getattr(settings, "GROQ_API_KEY", None)
            groq_model = getattr(settings, "AI_MODEL", "llama-3.1-8b-instant")
            gemini_api_key = getattr(settings, "GEMINI_API_KEY", None)
            gemini_model = getattr(settings, "AI_MODEL", "gemini-2.0-flash")
            ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
            ollama_model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:14b")

            # Try to load saved user config from DB
            try:
                from app.database.session import SessionLocal
                from app.database.models.user_settings import UserSettings
                from app.services.crypto import decrypt
                db = SessionLocal()
                s = db.query(UserSettings).filter(UserSettings.user_id == getattr(state, 'current_user_id', 0)).first()
                if s:
                    if s.ai_provider:
                        provider = s.ai_provider
                    if s.ai_model:
                        if provider == "groq":
                            groq_model = s.ai_model
                        elif provider == "gemini":
                            gemini_model = s.ai_model
                    if s.ai_groq_key_enc:
                        try:
                            groq_api_key = decrypt(s.ai_groq_key_enc)
                        except Exception:
                            pass
                    if s.ai_gemini_key_enc:
                        try:
                            gemini_api_key = decrypt(s.ai_gemini_key_enc)
                        except Exception:
                            pass
                    if s.ai_premium_key_enc:
                        # Premium key will be applied on start
                        try:
                            state.ai_premium_key = decrypt(s.ai_premium_key_enc)
                        except Exception:
                            pass
                    if s.ai_premium_provider:
                        state.ai_premium_provider = s.ai_premium_provider
                    if s.ai_premium_model:
                        state.ai_premium_model = s.ai_premium_model
                db.close()
            except Exception:
                pass

            state.ai_agent = AITradingAgent(
                provider=provider,
                groq_api_key=groq_api_key,
                groq_model=groq_model,
                gemini_api_key=gemini_api_key,
                gemini_model=gemini_model,
                ollama_url=ollama_url,
                ollama_model=ollama_model,
                interval_seconds=getattr(settings, "AI_INTERVAL_SECONDS", 30),
                auto_trade=getattr(settings, "AI_AUTO_TRADE", True),
                auth_server_url=getattr(settings, "AUTH_SERVER_URL", None),
            )
        return state.ai_agent
