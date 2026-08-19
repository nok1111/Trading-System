"""Trading query endpoints (signals, orders, positions, trades, backtests, snapshots)."""

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.config import get_settings
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

logger = logging.getLogger(__name__)
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


# ---------------------------------------------------------------------------
# Historical Data Cache — for extended backtesting periods
# ---------------------------------------------------------------------------


@router.get("/historical-data/status")
def get_historical_cache_status() -> dict:
    """Get status of cached historical data."""
    from app.services.historical_data_service import get_historical_data_service
    return get_historical_data_service().get_cache_status()


@router.post("/historical-data/fetch")
def fetch_historical_data(req: dict) -> dict:
    """Download and cache historical klines from Binance.

    Body: {symbol, timeframe, days}
    """
    from app.services.historical_data_service import get_historical_data_service
    symbol = req.get("symbol", "BTCUSDT")
    timeframe = req.get("timeframe", "1h")
    days = int(req.get("days", 365))
    return get_historical_data_service().fetch_and_cache(symbol, timeframe, days)


@router.get("/historical-data/{symbol}")
def get_cached_klines(
    symbol: str,
    timeframe: str = "1h",
    days: int = 365,
) -> dict:
    """Read cached klines from DB."""
    from datetime import UTC, datetime, timedelta
    from app.services.historical_data_service import get_historical_data_service
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)
    klines = get_historical_data_service().get_cached_klines(symbol, timeframe, start, end)
    return {"status": "ok", "symbol": symbol, "timeframe": timeframe, "count": len(klines), "klines": klines}


@router.delete("/historical-data/{symbol}")
def clear_historical_cache(symbol: str) -> dict:
    """Clear cached data for a symbol."""
    from app.services.historical_data_service import get_historical_data_service
    return get_historical_data_service().clear_cache(symbol)


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
    _notify_position_update(current_user.id)
    return {"id": pos.id, "auto_sell_enabled": pos.auto_sell_enabled}


class ClosePositionRequest(BaseModel):
    symbol: str
    broker_id: str | None = None
    quantity: float | None = None
    position_id: int | None = None


@router.post("/positions/close")
def close_broker_position(
    req: ClosePositionRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Close a broker-managed position at market price.

    Works for both DB positions (with position_id) and broker-managed
    positions (id=0, live holdings). Places a market SELL order via the
    broker adapter.
    """
    from app.api.helpers import get_shared_broker, resolve_binancekeys, resolve_broker_credentials
    from app.brokers.registry import get_adapter
    from app.brokers.models import OrderRequest, OrderSide, OrderType
    from decimal import Decimal as Dec

    symbol = req.symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    broker_id = req.broker_id or "binance"

    # If we have a DB position_id, close it in DB too
    db = SessionLocal()
    db_pos = None
    try:
        if req.position_id and req.position_id > 0:
            db_pos = db.query(Position).filter(
                Position.id == req.position_id,
                Position.user_id == current_user.id,
                Position.status == "open",
            ).first()
            if db_pos:
                symbol = db_pos.symbol.replace("/", "").replace("-", "").replace("_", "")
                qty = req.quantity or float(db_pos.quantity)
            else:
                return {"status": "error", "reason": "Position not found in DB"}
        else:
            qty = req.quantity
    finally:
        if not db_pos:
            db.close()

    # Get quantity from broker if not provided
    if not qty:
        try:
            creds = resolve_broker_credentials(broker_id, current_user=current_user)
            if creds:
                adapter = get_adapter(broker_id, creds)
                # Try get_open_positions (BinanceAdapter) or get_positions (CCXT)
                positions = []
                if hasattr(adapter, "get_open_positions"):
                    positions = adapter.get_open_positions()
                elif hasattr(adapter, "get_positions"):
                    positions = adapter.get_positions()
                for p in positions:
                    psym = p.symbol.replace("/", "").replace("-", "").replace("_", "").upper()
                    if psym == symbol:
                        qty = float(p.quantity)
                        break
        except Exception as exc:
            return {"status": "error", "reason": f"No se pudo obtener cantidad: {exc}"}

    if not qty or qty <= 0:
        return {"status": "error", "reason": "Cantidad no disponible o invalida"}

    # Place market SELL order via broker
    try:
        if broker_id == "binance":
            keys = resolve_binancekeys(current_user)
            if not keys:
                return {"status": "error", "reason": "No hay credenciales de Binance"}
            broker = get_shared_broker(keys)
            if hasattr(broker, "sell"):
                result = broker.sell(symbol, float(qty))
            elif hasattr(broker, "place_order"):
                order_req = OrderRequest(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=Dec(str(qty)),
                )
                adapter = broker
                if not hasattr(adapter, "place_order"):
                    from app.brokers.adapters.binance_adapter import BinanceAdapter
                    adapter = BinanceAdapter(broker)
                result = adapter.place_order(order_req)
            else:
                return {"status": "error", "reason": "Broker no soporta sell"}
        else:
            creds = resolve_broker_credentials(broker_id, current_user=current_user)
            if not creds:
                return {"status": "error", "reason": f"No hay credenciales para {broker_id}"}
            adapter = get_adapter(broker_id, creds)
            order_req = OrderRequest(
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=Dec(str(qty)),
            )
            result = adapter.place_order(order_req)

        # Update DB position if exists
        if db_pos:
            try:
                sell_price = 0.0
                if hasattr(result, "order") and result.order:
                    sell_price = float(result.order.avg_price or result.order.price or 0)
                if not sell_price:
                    from app.services.market_data_service import get_market_data_service
                    mds = get_market_data_service()
                    ticker = mds.get_ticker(symbol)
                    sell_price = float(ticker.price) if ticker else 0.0

                entry = float(db_pos.entry_price)
                realized_pnl = (sell_price - entry) * qty if db_pos.side == "long" else (entry - sell_price) * qty
                db_pos.status = "closed"
                db_pos.closed_at = datetime.now(tz=UTC)
                db_pos.current_price = Dec(str(sell_price))
                db_pos.realized_pnl = Dec(str(round(realized_pnl, 8)))
                meta = db_pos.metadata_json or {}
                meta["closed_by"] = "manual_sell"
                meta["broker_order"] = True
                db_pos.metadata_json = meta

                from app.database.models.trade import Trade
                trade = Trade(
                    user_id=current_user.id,
                    timestamp=datetime.now(tz=UTC),
                    symbol=db_pos.symbol,
                    side="SELL",
                    quantity=Dec(str(qty)),
                    price=Dec(str(sell_price)),
                    commission=Dec("0"),
                    slippage=Dec("0"),
                    realized_pnl=Dec(str(realized_pnl)),
                    strategy_name=db_pos.strategy_name,
                    position_id=db_pos.id,
                    broker_id=broker_id,
                    metadata_json={"source": "manual_sell"},
                )
                db.add(trade)
                db.commit()
                _notify_position_update(current_user.id)
            except Exception as exc:
                db.rollback()
                logger.warning("DB position update failed: %s", exc)
            finally:
                db.close()

        return {
            "status": "executed",
            "symbol": symbol,
            "quantity": qty,
            "broker_id": broker_id,
            "result": str(result) if result else "OK",
        }
    except Exception as exc:
        if db_pos:
            db.rollback()
            db.close()
        logger.error("Close position error: %s", exc)
        return {"status": "error", "reason": str(exc)}


class SetSlTpRequest(BaseModel):
    position_id: int | None = None
    symbol: str
    broker_id: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


@router.post("/positions/set-sl-tp")
def set_sl_tp(
    req: SetSlTpRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)] = None,
) -> dict:
    """Set stop-loss and/or take-profit on a position.

    For DB positions: updates the DB record and places OCO on broker if live.
    For broker-managed positions (id=0): places OCO order directly on broker.

    Accepts both absolute values (stop_loss=1836.80) and percentages
    (stop_loss_pct=3.0).
    """
    from app.api.helpers import resolve_binancekeys, resolve_broker_credentials
    from app.brokers.registry import get_adapter
    from decimal import Decimal as Dec

    symbol = req.symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    broker_id = req.broker_id or "binance"

    db = SessionLocal()
    try:
        # Find DB position
        db_pos = None
        if req.position_id and req.position_id > 0:
            db_pos = db.query(Position).filter(
                Position.id == req.position_id,
                Position.user_id == current_user.id,
                Position.status == "open",
            ).first()

        # Calculate absolute values from percentage if needed
        entry_price = 0.0
        if db_pos:
            entry_price = float(db_pos.entry_price)
        else:
            # Get entry from broker position
            try:
                creds = resolve_broker_credentials(broker_id, current_user=current_user)
                if creds:
                    adapter = get_adapter(broker_id, creds)
                    positions = []
                    if hasattr(adapter, "get_open_positions"):
                        positions = adapter.get_open_positions()
                    elif hasattr(adapter, "get_positions"):
                        positions = adapter.get_positions()
                    for p in positions:
                        psym = p.symbol.replace("/", "").replace("-", "").replace("_", "").upper()
                        if psym == symbol:
                            entry_price = float(p.entry_price or 0)
                            break
            except Exception:
                pass

        if entry_price <= 0:
            # Get current market price as fallback
            try:
                from app.services.market_data_service import get_market_data_service
                mds = get_market_data_service()
                ticker = mds.get_ticker(symbol)
                entry_price = float(ticker.price) if ticker else 0.0
            except Exception:
                pass

        sl = req.stop_loss
        tp = req.take_profit
        if sl is None and req.stop_loss_pct is not None and entry_price > 0:
            sl = round(entry_price * (1 - req.stop_loss_pct / 100), 8)
        if tp is None and req.take_profit_pct is not None and entry_price > 0:
            tp = round(entry_price * (1 + req.take_profit_pct / 100), 8)

        # Update DB position if exists
        if db_pos:
            if sl is not None:
                db_pos.stop_loss = Dec(str(sl))
            if tp is not None:
                db_pos.take_profit = Dec(str(tp))
            db.commit()
            _notify_position_update(current_user.id)

        # Place OCO on broker if live trading
        broker_placed = False
        try:
            settings = get_settings()
            if settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED:
                if broker_id == "binance":
                    keys = resolve_binancekeys(current_user)
                    if keys:
                        from app.api.helpers import get_shared_broker
                        broker = get_shared_broker(keys)
                        adapter = broker
                        if not hasattr(adapter, "place_oco_order"):
                            from app.brokers.adapters.binance_adapter import BinanceAdapter
                            adapter = BinanceAdapter(broker)
                        if hasattr(adapter, "place_oco_order") and sl and tp:
                            qty = float(db_pos.quantity) if db_pos else 0
                            if not qty:
                                creds = resolve_broker_credentials(broker_id, current_user=current_user)
                                if creds:
                                    ba = get_adapter(broker_id, creds)
                                    ba_positions = []
                                    if hasattr(ba, "get_open_positions"):
                                        ba_positions = ba.get_open_positions()
                                    elif hasattr(ba, "get_positions"):
                                        ba_positions = ba.get_positions()
                                    for p in ba_positions:
                                        psym = p.symbol.replace("/", "").replace("-", "").replace("_", "").upper()
                                        if psym == symbol:
                                            qty = float(p.quantity)
                                            break
                            if qty > 0:
                                adapter.place_oco_order(symbol, qty, Dec(str(sl)), Dec(str(tp)))
                                broker_placed = True
        except Exception as exc:
            logger.warning("Broker OCO placement failed: %s", exc)

        return {
            "status": "executed",
            "symbol": symbol,
            "stop_loss": sl,
            "take_profit": tp,
            "broker_oco": broker_placed,
            "position_id": db_pos.id if db_pos else None,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Set SL/TP error: %s", exc)
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()


def _notify_position_update(user_id: int):
    """Notify WebSocket subscribers that positions changed."""
    try:
        from app.api.routes.realtime import notify_position_update
        notify_position_update(user_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

@router.get("/trades/export")
def export_trades(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    start_date: str | None = Query(None, description="ISO date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="ISO date (YYYY-MM-DD)"),
) -> StreamingResponse:
    """Export trades as CSV for tax/accounting purposes.

    Columns: date, symbol, side, quantity, price, fee, pnl, broker, order_id
    """
    import csv
    import io

    db = SessionLocal()
    try:
        query = db.query(Trade).filter(Trade.user_id == current_user.id)
        if start_date:
            query = query.filter(Trade.timestamp >= start_date)
        if end_date:
            query = query.filter(Trade.timestamp <= end_date + " 23:59:59")
        trades = query.order_by(Trade.timestamp.desc()).all()
    finally:
        db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "symbol", "side", "quantity", "price", "fee", "pnl", "broker", "order_id"])

    for t in trades:
        writer.writerow([
            t.timestamp.isoformat() if t.timestamp else "",
            t.symbol or "",
            t.side or "",
            str(t.quantity) if t.quantity else "",
            str(t.price) if t.price else "",
            str(t.fee) if t.fee else "",
            str(t.pnl) if t.pnl else "",
            getattr(t, "broker_id", "") or "",
            getattr(t, "order_id", "") or "",
        ])

    output.seek(0)

    filename = f"alvora_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
