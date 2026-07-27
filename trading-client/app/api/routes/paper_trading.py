"""Paper trading endpoints."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import app.api.state as state
from app.api.helpers import build_strategy
from app.config import get_settings
from app.database.session import SessionLocal

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])


class PaperTradingStartRequest(BaseModel):
    """Payload para iniciar paper trading."""
    strategies: list[str] = ["trend"]  # "trend", "ml", o ambas
    timeframe: str | None = None  # ej: "5m", "15m", "1h", "1d"
    interval_seconds: int | None = None  # intervalo entre ticks (min 5s)


class DepositRequest(BaseModel):
    """Payload para depositar fondos en la cuenta de paper trading."""
    amount: float


class SellRequest(BaseModel):
    """Payload para cerrar una posicion manualmente."""
    symbol: str


class HoldRequest(BaseModel):
    """Payload para togglear hold en una posicion."""
    symbol: str
    hold: bool = True


class IntervalRequest(BaseModel):
    """Payload para cambiar el intervalo de ticks."""
    interval_seconds: int


@router.post("/start")
def paper_trading_start(req: PaperTradingStartRequest | None = None) -> dict:
    """Inicia paper trading desde la API."""
    if state.paper_trading_state["schedulers"]:
        return {"status": "already_running", "run_ids": state.paper_trading_state["run_ids"]}

    from app.data import MarketDataService
    from app.factories import create_broker, create_data_source
    from app.paper_trading import PaperTradingScheduler
    from app.risk import RiskManager

    settings = get_settings()
    if not settings.PAPER_TRADING_ENABLED:
        raise HTTPException(status_code=400, detail="PAPER_TRADING_ENABLED=false")

    strategy_names = req.strategies if req else ["trend"]
    if not strategy_names:
        strategy_names = ["trend"]

    if req and req.timeframe:
        settings.DATA_TIMEFRAME = req.timeframe
    if req and req.interval_seconds and req.interval_seconds >= 5:
        settings.PAPER_TRADING_INTERVAL_SECONDS = req.interval_seconds

    schedulers = []
    run_ids = []
    from app.brokers import MockBroker
    shared_broker = MockBroker(initial_cash=settings.PAPER_TRADING_INITIAL_CASH)
    # Sync broker state from DB open positions (handles restarts)
    from app.database.models.position import Position as PosModel
    sync_session = SessionLocal()
    try:
        open_pos = sync_session.query(PosModel).filter_by(status="open").all()
        if open_pos:
            shared_broker.sync_from_db(open_pos, settings.PAPER_TRADING_INITIAL_CASH)
    finally:
        sync_session.close()
    for name in strategy_names:
        strategy = build_strategy(name, settings)
        scheduler = PaperTradingScheduler(
            settings=settings,
            strategy=strategy,
            data_service=MarketDataService(create_data_source(settings)),
            broker=shared_broker,
            risk_manager=RiskManager(settings),
            session_factory=SessionLocal,
        )
        run = scheduler.start()
        schedulers.append(scheduler)
        run_ids.append(run.id)

    state.paper_trading_state["schedulers"] = schedulers
    state.paper_trading_state["run_ids"] = run_ids
    return {"status": "started", "run_ids": run_ids, "strategies": strategy_names}


@router.post("/stop")
def paper_trading_stop() -> dict:
    """Detiene paper trading desde la API."""
    schedulers = state.paper_trading_state["schedulers"]
    if not schedulers:
        return {"status": "not_running", "run_ids": []}
    run_ids = state.paper_trading_state["run_ids"]
    for scheduler in schedulers:
        try:
            scheduler.stop()
        except Exception:
            pass
    state.paper_trading_state["schedulers"] = []
    state.paper_trading_state["run_ids"] = []
    return {"status": "stopped", "run_ids": run_ids}


@router.get("/status")
def paper_trading_status() -> dict:
    """Estado del paper trading."""
    settings = get_settings()
    schedulers = state.paper_trading_state["schedulers"]
    interval = settings.PAPER_TRADING_INTERVAL_SECONDS
    if not schedulers:
        return {"status": "stopped", "run_ids": [], "local_time": settings.now_local().strftime("%Y-%m-%d %H:%M:%S %Z"), "interval_seconds": interval}
    any_running = any(s.is_running for s in schedulers)
    return {"status": "running" if any_running else "stopped", "run_ids": state.paper_trading_state["run_ids"], "local_time": settings.now_local().strftime("%Y-%m-%d %H:%M:%S %Z"), "interval_seconds": interval}


@router.patch("/interval")
def paper_trading_set_interval(req: IntervalRequest) -> dict:
    """Cambia el intervalo de ticks del paper trading en tiempo real."""
    if req.interval_seconds < 5:
        raise HTTPException(status_code=400, detail="El intervalo mínimo es 5 segundos")
    settings = get_settings()
    settings.PAPER_TRADING_INTERVAL_SECONDS = req.interval_seconds
    schedulers = state.paper_trading_state["schedulers"]
    for scheduler in schedulers:
        scheduler.set_interval(req.interval_seconds)
    return {"status": "ok", "interval_seconds": req.interval_seconds}


@router.post("/deposit")
def paper_trading_deposit(req: DepositRequest) -> dict:
    """Deposita fondos en la cuenta de paper trading activa."""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser positivo")
    schedulers = state.paper_trading_state["schedulers"]
    if not schedulers:
        raise HTTPException(status_code=400, detail="Paper trading no está activo")
    results = []
    for scheduler in schedulers:
        broker = scheduler.broker
        if hasattr(broker, "deposit"):
            new_cash = broker.deposit(Decimal(str(req.amount)))
            results.append({"broker": broker.name, "cash": str(new_cash)})
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Broker {broker.name} no soporta depósitos",
            )
    return {"status": "deposited", "amount": req.amount, "accounts": results}


@router.post("/sell")
def paper_trading_sell(req: SellRequest) -> dict:
    """Cierra una posicion manualmente por simbolo."""
    schedulers = state.paper_trading_state["schedulers"]
    if not schedulers:
        raise HTTPException(status_code=400, detail="Paper trading no está activo")
    results = []
    for scheduler in schedulers:
        result = scheduler.manual_sell(req.symbol)
        results.append(result)
    return {"status": "sell_completed", "symbol": req.symbol, "results": results}


@router.post("/hold")
def paper_trading_hold(req: HoldRequest) -> dict:
    """Togglear hold en una posicion para que la IA no la venda."""
    from app.database.models.position import Position as PosModel
    session = SessionLocal()
    try:
        pos = session.query(PosModel).filter_by(symbol=req.symbol, status="open").first()
        if pos is None:
            raise HTTPException(status_code=404, detail=f"No hay posicion abierta en {req.symbol}")
        meta = pos.metadata_json or {}
        meta["hold"] = req.hold
        pos.metadata_json = meta
        session.add(pos)
        session.commit()
        return {"status": "ok", "symbol": req.symbol, "hold": req.hold}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
