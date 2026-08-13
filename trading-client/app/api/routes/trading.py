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
    # ─── Merge broker-live orders with DB orders ────────────────────────
    from app.brokers.models import normalize_symbol
    from app.brokers.registry import get_adapter
    from app.api.helpers import resolve_broker_credentials
    from app.database.models.broker_account import BrokerAccount

    # Get DB orders (for paper trading and app-managed orders)
    query = db.query(Order).filter(Order.user_id == current_user.id)
    if symbol:
        query = query.filter(Order.symbol == symbol.upper())
    db_orders = query.order_by(Order.id.desc()).offset(skip).limit(limit).all()

    # Normalize symbols in DB orders
    for o in db_orders:
        o.symbol = normalize_symbol(o.symbol)

    # Fetch orders from all connected brokers
    connected_brokers = db.query(BrokerAccount).filter(
        BrokerAccount.user_id == current_user.id,
    ).all()

    broker_orders: list[Order] = []
    existing_keys: set[str] = set()
    for o in db_orders:
        key = f"{o.broker_order_id}:{o.symbol}" if o.broker_order_id else f"db:{o.id}"
        existing_keys.add(key)

    for ba in connected_brokers:
        try:
            creds = resolve_broker_credentials(ba.broker_id, current_user)
            if not creds:
                continue
            adapter = get_adapter(ba.broker_id, creds)
            broker_syms = symbol if symbol else None
            raw_orders = adapter.get_order_history(symbol=broker_syms, limit=limit)
            for bo in raw_orders:
                sym = normalize_symbol(bo.symbol)
                key = f"{bo.broker_order_id}:{sym}" if bo.broker_order_id else ""
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                # Create transient Order object from broker data
                broker_orders.append(Order(
                    id=0,
                    user_id=current_user.id,
                    broker_id=ba.broker_id,
                    client_order_id=bo.client_order_id or "",
                    idempotency_key=f"broker_{bo.broker_order_id or bo.client_order_id or ''}",
                    broker_order_id=bo.broker_order_id,
                    timestamp=bo.created_at or datetime.now(UTC),
                    symbol=sym,
                    side=bo.side.value,
                    order_type=bo.order_type.value,
                    quantity=bo.quantity,
                    filled_quantity=bo.filled_quantity,
                    price=bo.price,
                    status=bo.status.value,
                    internal_status="RECONCILED",
                    signal_id=None,
                    created_at=bo.created_at or datetime.now(UTC),
                ))
        except Exception:
            continue

    # Merge and sort by timestamp desc
    all_orders = list(db_orders) + broker_orders
    all_orders.sort(key=lambda o: o.created_at or o.timestamp or datetime.min.replace(tzinfo=UTC), reverse=True)
    return all_orders[:limit]


@router.get("/positions", response_model=list[PositionOut])
def list_positions(
    db: DbSession,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    status: StatusQuery = None,
) -> list[Position]:
    query = db.query(Position).filter(
        (Position.user_id == current_user.id) | (Position.user_id == 0)
    )
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

    # ─── Merge broker-live positions (futures + spot holdings) ──────────
    # Fetch real positions from all connected brokers and merge with DB.
    # DB positions that match a broker position get updated; new broker-only
    # positions get added to the result list.
    from app.database.models.position import Position as DBPosition
    from app.brokers.base import BrokerError

    broker_live_positions: list[DBPosition] = []
    existing_symbols: set[str] = {p.symbol for p in positions if p.status == "open"}

    # Get all unique broker_ids from DB positions
    broker_ids = set(p.broker_id for p in positions if p.broker_id and p.status == "open")
    # Also check connected brokers
    from app.database.models.broker_account import BrokerAccount
    connected_brokers = db.query(BrokerAccount).filter(
        BrokerAccount.user_id == current_user.id,
    ).all()
    broker_ids.update(b.broker_id for b in connected_brokers)

    for bid in broker_ids:
        adapter = broker_adapter_cache.get(bid)
        if not adapter:
            try:
                creds = resolve_broker_credentials(bid, current_user)
                if creds:
                    adapter = get_adapter(bid, creds)
                    broker_adapter_cache[bid] = adapter
            except Exception:
                continue
        if not adapter:
            continue

        try:
            broker_positions = adapter.get_open_positions()
            # If no futures positions, try spot holdings
            if not broker_positions:
                STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "UST", "TUSD", "FDUSD", "USDP", "EUR"}
                balances = adapter.get_account_balances()
                for bal in balances:
                    if bal.asset in STABLECOINS or bal.total <= 0:
                        continue
                    current_price = None
                    for quote in ("USDT", "USDC", "USD"):
                        try:
                            ticker = adapter.get_ticker(f"{bal.asset}/{quote}")
                            current_price = ticker.price
                            break
                        except Exception:
                            continue
                    # Fetch entry price from trade history
                    entry_price = Decimal("0")
                    try:
                        sym = normalize_symbol(f"{bal.asset}/USDT")
                        trades = adapter.get_trades(symbol=sym, limit=500)
                        buy_trades = [t for t in trades if t.side.value == "buy"]
                        if buy_trades:
                            total_cost = sum(float(t.price) * float(t.quantity) for t in buy_trades)
                            total_qty = sum(float(t.quantity) for t in buy_trades)
                            if total_qty > 0:
                                entry_price = Decimal(str(round(total_cost / total_qty, 8)))
                    except Exception:
                        pass
                    unrealized = Decimal("0")
                    if entry_price > 0 and current_price:
                        unrealized = Decimal(str(round(
                            (float(current_price) - float(entry_price)) * float(bal.total), 8
                        )))
                    from app.brokers.models import Position as BrokerPosition
                    broker_positions = broker_positions + (
                        BrokerPosition(
                            symbol=f"{bal.asset}/USDT",
                            side="long",
                            quantity=bal.total,
                            entry_price=entry_price,
                            current_price=current_price,
                            unrealized_pnl=unrealized,
                            status="open",
                            strategy_name="spot_holding",
                            metadata={"source": "broker_balance"},
                        ),
                    )

            for bpos in broker_positions:
                sym = normalize_symbol(bpos.symbol)
                if sym in existing_symbols:
                    # Update existing DB position with broker data
                    for p in positions:
                        if p.symbol == sym and p.status == "open":
                            if bpos.current_price:
                                p.current_price = bpos.current_price
                            if bpos.unrealized_pnl:
                                p.unrealized_pnl = bpos.unrealized_pnl
                            break
                else:
                    # New position from broker not in DB — create a transient object
                    np = DBPosition(
                        id=0,
                        user_id=current_user.id,
                        broker_id=bid,
                        symbol=sym,
                        side=bpos.side,
                        quantity=bpos.quantity,
                        entry_price=bpos.entry_price,
                        current_price=bpos.current_price,
                        unrealized_pnl=bpos.unrealized_pnl,
                        realized_pnl=Decimal("0"),
                        stop_loss=None,
                        take_profit=None,
                        status="open",
                        strategy_name=bpos.strategy_name or "broker_live",
                        opened_at=bpos.opened_at or datetime.now(UTC),
                        created_at=datetime.now(UTC),
                    )
                    broker_live_positions.append(np)
                    existing_symbols.add(sym)
        except Exception:
            continue

    # Merge broker-live positions with DB positions
    all_positions = list(positions) + broker_live_positions

    # Sort: open first, then by id desc
    all_positions.sort(
        key=lambda p: (0 if p.status == "open" else 1, -p.id),
    )

    return all_positions[:limit]


@router.get("/trades", response_model=list[TradeOut])
def list_trades(
    db: DbSession,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[Trade]:
    # ─── Merge broker-live trades with DB trades ────────────────────────
    from app.brokers.models import normalize_symbol
    from app.brokers.registry import get_adapter
    from app.api.helpers import resolve_broker_credentials
    from app.database.models.broker_account import BrokerAccount

    # Get DB trades (for paper trading and app-managed trades)
    query = db.query(Trade).filter(Trade.user_id == current_user.id)
    if symbol:
        query = query.filter(Trade.symbol == symbol.upper())
    db_trades = query.order_by(Trade.id.desc()).offset(skip).limit(limit).all()

    # Normalize symbols in DB trades
    for t in db_trades:
        t.symbol = normalize_symbol(t.symbol)

    # Fetch trades from all connected brokers
    connected_brokers = db.query(BrokerAccount).filter(
        BrokerAccount.user_id == current_user.id,
    ).all()

    broker_trades: list[Trade] = []
    existing_keys: set[str] = set()
    for t in db_trades:
        existing_keys.add(f"db:{t.id}")

    for ba in connected_brokers:
        try:
            creds = resolve_broker_credentials(ba.broker_id, current_user)
            if not creds:
                continue
            adapter = get_adapter(ba.broker_id, creds)
            broker_syms = symbol if symbol else None
            raw_trades = adapter.get_trades(symbol=broker_syms, limit=limit)
            for bt in raw_trades:
                sym = normalize_symbol(bt.symbol)
                key = f"broker:{bt.broker_trade_id}"
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                # Create transient Trade object from broker data
                broker_trades.append(Trade(
                    id=0,
                    user_id=current_user.id,
                    broker_id=ba.broker_id,
                    timestamp=bt.timestamp or datetime.now(UTC),
                    symbol=sym,
                    side=bt.side.value,
                    quantity=bt.quantity,
                    price=bt.price,
                    commission=bt.fee.amount if bt.fee else Decimal("0"),
                    slippage=Decimal("0"),
                    realized_pnl=Decimal("0"),
                    strategy_name="broker_live",
                    order_id=None,
                    position_id=None,
                    metadata_json={"broker_trade_id": bt.broker_trade_id, "broker_order_id": bt.broker_order_id},
                    created_at=bt.timestamp or datetime.now(UTC),
                ))
        except Exception:
            continue

    # Merge and sort by timestamp desc
    all_trades = list(db_trades) + broker_trades
    all_trades.sort(key=lambda t: t.timestamp or datetime.min.replace(tzinfo=UTC), reverse=True)
    return all_trades[:limit]


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
