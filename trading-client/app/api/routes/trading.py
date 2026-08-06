"""Trading query endpoints (signals, orders, positions, trades, backtests, snapshots)."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.api.schemas import (
    AccountSnapshotOut,
    BacktestRunOut,
    OrderOut,
    PositionOut,
    SignalOut,
    StrategyRunOut,
    TradeOut,
)
from app.database.models import (
    AccountSnapshot,
    BacktestRun,
    Order,
    Position,
    Signal,
    StrategyRun,
    Trade,
)
from app.database.session import SessionLocal
from app.services.auth import LocalUser, get_current_user

router = APIRouter(prefix="/api", tags=["trading"])


def get_db() -> Generator[Session, None, None]:
    """Dependencia que provee una sesión de BD por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
PaginateSkip = Annotated[int, Query(ge=0)]
PaginateLimit = Annotated[int, Query(ge=1, le=200)]
SymbolQuery = Annotated[str | None, Query()]
StatusQuery = Annotated[str | None, Query()]
RunIdQuery = Annotated[int | None, Query()]


@router.get("/strategy-runs", response_model=list[StrategyRunOut])
def list_strategy_runs(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
) -> list[StrategyRun]:
    return db.query(StrategyRun).order_by(StrategyRun.id.desc()).offset(skip).limit(limit).all()


@router.get("/strategy-runs/{run_id}", response_model=StrategyRunOut)
def get_strategy_run(run_id: int, db: DbSession) -> StrategyRun:
    run = db.get(StrategyRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="StrategyRun not found")
    return run


@router.get("/signals", response_model=list[SignalOut])
def list_signals(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Signal]:
    query = db.query(Signal)
    if symbol:
        query = query.filter(Signal.symbol == symbol.upper())
    return query.order_by(Signal.id.desc()).offset(skip).limit(limit).all()


class ManualSignalRequest(BaseModel):
    """Payload para importar una señal manual."""
    symbol: str
    signal_type: str  # BUY, SELL, HOLD
    entry_price: float | None = None
    confidence: float = 1.0
    explanation: str = ""


@router.post("/signals", response_model=SignalOut, status_code=201)
def create_signal(req: ManualSignalRequest, db: DbSession) -> Signal:
    """Importa una señal manual para trackear trends."""
    signal = Signal(
        timestamp=datetime.now(tz=UTC),
        symbol=req.symbol.upper(),
        signal_type=req.signal_type.upper(),
        confidence=Decimal(str(req.confidence)),
        entry_price=Decimal(str(req.entry_price)) if req.entry_price else None,
        suggested_stop_loss=None,
        suggested_take_profit=None,
        strategy_name="Manual",
        explanation=req.explanation or "Señal importada manualmente",
        metadata_json={"source": "manual"},
        status="active",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


@router.delete("/signals/{signal_id}")
def delete_signal(signal_id: int, db: DbSession) -> dict:
    """Elimina una señal por ID."""
    signal = db.get(Signal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    db.delete(signal)
    db.commit()
    return {"status": "deleted", "id": signal_id}


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    db: DbSession,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Order]:
    query = db.query(Order).filter(Order.user_id == current_user.id)
    if symbol:
        query = query.filter(Order.symbol == symbol.upper())
    return query.order_by(Order.id.desc()).offset(skip).limit(limit).all()


@router.get("/positions", response_model=list[PositionOut])
def list_positions(
    db: DbSession,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    status: StatusQuery = None,
) -> list[Position]:
    query = db.query(Position).filter(Position.user_id == current_user.id)
    if status:
        query = query.filter(Position.status == status.lower())
    # Sort: open positions first, then by id desc
    positions = query.order_by(
        case((Position.status == "open", 0), else_=1),
        Position.id.desc(),
    ).offset(skip).limit(limit).all()

    # Normalize symbols (BTCUSDT -> BTC/USDT) and update live prices for open positions
    from app.brokers.models import normalize_symbol
    from app.brokers.registry import get_adapter
    from app.api.helpers import resolve_broker_credentials

    # Cache adapters per broker to avoid re-creating for each position
    broker_adapter_cache: dict[str, any] = {}
    for p in positions:
        # Normalize symbol in-place
        p.symbol = normalize_symbol(p.symbol)

        # Update live price for open positions
        if p.status == "open" and p.broker_id:
            try:
                if p.broker_id not in broker_adapter_cache:
                    creds = resolve_broker_credentials(p.broker_id, current_user)
                    if creds:
                        broker_adapter_cache[p.broker_id] = get_adapter(p.broker_id, creds)
                    else:
                        broker_adapter_cache[p.broker_id] = None

                adapter = broker_adapter_cache.get(p.broker_id)
                if adapter:
                    ticker = adapter.get_ticker(p.symbol)
                    live_price = float(ticker.price)
                    p.current_price = Decimal(str(live_price))
                    if p.side == "long":
                        p.unrealized_pnl = Decimal(str((live_price - float(p.entry_price)) * float(p.quantity)))
                    else:
                        p.unrealized_pnl = Decimal(str((float(p.entry_price) - live_price) * float(p.quantity)))
            except Exception:
                pass  # Keep DB value if broker fetch fails

    # Commit any price updates
    try:
        db.commit()
    except Exception:
        db.rollback()

    return positions


@router.get("/trades", response_model=list[TradeOut])
def list_trades(
    db: DbSession,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Trade]:
    query = db.query(Trade).filter(Trade.user_id == current_user.id)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    return query.order_by(Trade.id.desc()).offset(skip).limit(limit).all()


@router.get("/backtests", response_model=list[BacktestRunOut])
def list_backtests(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
) -> list[BacktestRun]:
    return db.query(BacktestRun).order_by(BacktestRun.id.desc()).offset(skip).limit(limit).all()


@router.get("/backtests/{run_id}", response_model=BacktestRunOut)
def get_backtest(run_id: int, db: DbSession) -> BacktestRun:
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="BacktestRun not found")
    return run


@router.get("/snapshots", response_model=list[AccountSnapshotOut])
def list_snapshots(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    strategy_run_id: RunIdQuery = None,
) -> list[AccountSnapshot]:
    query = db.query(AccountSnapshot)
    if strategy_run_id is not None:
        query = query.filter(AccountSnapshot.strategy_run_id == strategy_run_id)
    return query.order_by(AccountSnapshot.id.desc()).offset(skip).limit(limit).all()


@router.patch("/positions/{position_id}/auto-sell")
def toggle_auto_sell(
    position_id: int,
    enabled: bool = Query(True),
    db: DbSession = None,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Toggle auto-sell for a specific position."""
    pos = db.query(Position).filter(
        Position.id == position_id,
        Position.user_id == current_user.id,
    ).first()
    if pos is None:
        raise HTTPException(status_code=404, detail="Position not found")
    pos.auto_sell_enabled = enabled
    db.commit()
    return {"id": pos.id, "auto_sell_enabled": pos.auto_sell_enabled}
