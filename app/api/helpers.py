"""Shared helper functions across API routers."""

from fastapi import HTTPException

from app.config import get_settings
from app.database.session import SessionLocal
from app.services.crypto import decrypt


def resolve_binance_keys(current_user=None) -> tuple[str, str] | None:
    """Resolve Binance API keys: user stored > .env fallback. Returns (key, secret) or None."""
    if current_user and current_user.binance_api_key_enc:
        try:
            key = decrypt(current_user.binance_api_key_enc)
            secret = decrypt(current_user.binance_api_secret_enc)
            if key and secret:
                return (key, secret)
        except Exception:
            pass
    settings = get_settings()
    if settings.BROKER_API_KEY and settings.BROKER_API_SECRET:
        return (settings.BROKER_API_KEY, settings.BROKER_API_SECRET)
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

    # Si cambian las keys, recrear el broker
    if state.ai_shared_broker is not None and state.ai_shared_broker_keys == binance_keys:
        return state.ai_shared_broker

    # Crear broker usando la factory (MockBroker o BinanceBroker según config)
    from app.database.models.position import Position as PosModel
    from app.factories import create_broker

    settings = get_settings()

    if binance_keys:
        # Override settings with user keys
        from app.config import Settings
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
            state.ai_agent = AITradingAgent(
                provider=getattr(settings, "AI_PROVIDER", "groq"),
                groq_api_key=getattr(settings, "GROQ_API_KEY", None),
                groq_model=getattr(settings, "AI_MODEL", "llama-3.1-8b-instant"),
                gemini_api_key=getattr(settings, "GEMINI_API_KEY", None),
                gemini_model=getattr(settings, "AI_MODEL", "gemini-2.0-flash"),
                ollama_url=getattr(settings, "OLLAMA_URL", "http://localhost:11434"),
                ollama_model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:14b"),
                interval_seconds=getattr(settings, "AI_INTERVAL_SECONDS", 30),
                auto_trade=getattr(settings, "AI_AUTO_TRADE", True),
            )
        return state.ai_agent
