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

    # Auto-import from Binance if user has no local positions but has broker keys
    if not positions:
        from app.api.helpers import resolve_broker_credentials
        creds = resolve_broker_credentials("binance", current_user)
        if creds:
            try:
                from app.brokers.adapters.binance_adapter import BinanceAdapter
                from app.database.models.position import Position as PositionModel

                adapter = BinanceAdapter(creds)
                broker = adapter._broker
                imported = []

                # Spot holdings
                try:
                    account = broker._signed_request("GET", "/api/v3/account", {})
                    balances = account.get("balances", [])
                    import httpx as _httpx
                    price_map: dict[str, float] = {}
                    try:
                        tickers = _httpx.get("https://api.binance.com/api/v3/ticker/price", timeout=10).json()
                        for t in tickers:
                            price_map[t["symbol"]] = float(t["price"])
                    except Exception:
                        pass

                    stablecoins = {"USDT", "BUSD", "USDC", "UST", "TUSD", "FDUSD"}
                    for b in balances:
                        asset = b["asset"]
                        total = float(b["free"]) + float(b["locked"])
                        if total <= 0 or asset in stablecoins:
                            continue
                        symbol = f"{asset}USDT"
                        price = price_map.get(symbol, 0.0)
                        if price <= 0:
                            continue
                        pos = PositionModel(
                            user_id=current_user.id,
                            symbol=symbol,
                            opened_at=datetime.now(tz=UTC),
                            side="long",
                            quantity=Decimal(str(total)),
                            entry_price=Decimal(str(price)),
                            current_price=Decimal(str(price)),
                            unrealized_pnl=Decimal("0"),
                            status="open",
                            strategy_name="imported_binance",
                            metadata_json={"source": "binance_spot_import", "asset": asset},
                        )
                        db.add(pos)
                        imported.append(symbol)
                except Exception:
                    pass

                # Futures positions
                try:
                    fapi_resp = broker._signed_request("GET", "/fapi/v2/positionRisk", {})
                    for p in fapi_resp:
                        amt = float(p.get("positionAmt", 0))
                        if amt == 0:
                            continue
                        symbol = p.get("symbol", "")
                        entry = float(p.get("entryPrice", 0))
                        mark = float(p.get("markPrice", 0))
                        side = "long" if amt > 0 else "short"
                        qty = abs(amt)
                        pos = PositionModel(
                            user_id=current_user.id,
                            symbol=symbol,
                            opened_at=datetime.now(tz=UTC),
                            side=side,
                            quantity=Decimal(str(qty)),
                            entry_price=Decimal(str(entry)),
                            current_price=Decimal(str(mark)),
                            unrealized_pnl=Decimal(str((mark - entry) * qty if side == "long" else (entry - mark) * qty)),
                            status="open",
                            strategy_name="imported_binance",
                            metadata_json={"source": "binance_futures_import"},
                        )
                        db.add(pos)
                        imported.append(symbol)
                except Exception:
                    pass

                if imported:
                    db.commit()
                    # Re-query with the new positions
                    positions = query.order_by(
                        case((Position.status == "open", 0), else_=1),
                        Position.id.desc(),
                    ).offset(skip).limit(limit).all()
            except Exception:
                db.rollback()

    # Update current_price and unrealized_pnl for open positions
    open_positions = [p for p in positions if p.status == "open"]
    if open_positions:
        from decimal import Decimal as Dec

        from app.brokers.adapters.binance_adapter import BinanceAdapter
        from app.brokers.models import BrokerCredentials, normalize_symbol
        from app.config import get_settings

        from app.api.helpers import resolve_broker_credentials
        creds = resolve_broker_credentials("binance", current_user)

        updated = False
        for pos in open_positions:
            try:
                live = None
                if creds:
                    adapter = BinanceAdapter(creds)
                    try:
                        ticker = adapter.get_ticker(normalize_symbol(pos.symbol))
                        live = ticker.price
                    except Exception:
                        pass
                if live and live > 0:
                    pos.current_price = Dec(str(live))
                    pos.unrealized_pnl = (Dec(str(live)) - pos.entry_price) * pos.quantity
                    updated = True
            except Exception:
                pass
        if updated:
            db.commit()

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
