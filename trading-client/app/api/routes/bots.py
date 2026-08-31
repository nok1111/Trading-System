"""API endpoints para Grid y DCA bots — CRUD + start/stop + status."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_current_user
from app.database.session import SessionLocal
from app.database.models.grid_bot import DCABot, GridBot, ScalpBot, ScalpBotLog

router = APIRouter(prefix="/api/bots", tags=["bots"])


# ─── Pydantic schemas ───

class GridBotCreate(BaseModel):
    name: str
    broker_id: str = "binance"
    symbol: str
    market_type: str = "spot"
    lower_price: float
    upper_price: float
    grid_count: int = 10
    investment_usd: float


class GridBotUpdate(BaseModel):
    name: str | None = None
    lower_price: float | None = None
    upper_price: float | None = None
    grid_count: int | None = None
    investment_usd: float | None = None


class DCABotCreate(BaseModel):
    name: str
    broker_id: str = "binance"
    symbol: str
    market_type: str = "spot"
    buy_amount_usd: float
    interval_minutes: int = 1440
    max_buys: int = 0
    take_profit_pct: float = 0


class DCABotUpdate(BaseModel):
    name: str | None = None
    buy_amount_usd: float | None = None
    interval_minutes: int | None = None
    max_buys: int | None = None
    take_profit_pct: float | None = None


class ScalpBotCreate(BaseModel):
    name: str
    broker_id: str = "binance"
    max_capital_usd: float = 100
    risk_per_trade_pct: float = 20
    leverage: int = 3
    tp_pct: float = 0.50
    sl_pct: float = 0.35
    max_daily_loss_usd: float = 15
    min_atr_pct: float = 0.80
    max_hold_minutes: int = 20
    ai_refresh_sec: int = 180
    use_ai_filter: bool = True


def _scalp_to_dict(b: ScalpBot) -> dict:
    wins = b.wins or 0
    losses = b.losses or 0
    total = wins + losses
    winrate = (wins / total * 100) if total else 0
    return {
        "id": b.id,
        "name": b.name,
        "broker_id": b.broker_id,
        "max_capital_usd": str(b.max_capital_usd),
        "risk_per_trade_pct": str(b.risk_per_trade_pct),
        "leverage": b.leverage,
        "tp_pct": str(b.tp_pct),
        "sl_pct": str(b.sl_pct),
        "max_daily_loss_usd": str(b.max_daily_loss_usd),
        "min_atr_pct": str(b.min_atr_pct),
        "max_hold_minutes": b.max_hold_minutes,
        "ai_refresh_sec": b.ai_refresh_sec,
        "use_ai_filter": b.use_ai_filter,
        "is_active": b.is_active,
        "status": b.status,
        "last_heartbeat_at": b.last_heartbeat_at.isoformat() if b.last_heartbeat_at else None,
        "last_run_at": b.last_run_at.isoformat() if b.last_run_at else None,
        "trades_count": b.trades_count,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 1),
        "realized_pnl": str(b.realized_pnl),
        "daily_pnl": str(b.daily_pnl),
        "current_symbol": b.current_symbol,
        "current_side": b.current_side,
        "current_qty": str(b.current_qty) if b.current_qty is not None else None,
        "current_entry": str(b.current_entry) if b.current_entry is not None else None,
        "current_sl": str(b.current_sl) if b.current_sl is not None else None,
        "current_tp": str(b.current_tp) if b.current_tp is not None else None,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


# ─── Grid Bot endpoints ───

@router.get("/grid")
def list_grid_bots(user=Depends(get_current_user)):
    """List all grid bots for the user."""
    session = SessionLocal()
    try:
        bots = session.query(GridBot).filter_by(user_id=user.id).order_by(GridBot.created_at.desc()).all()
        return [
            {
                "id": b.id,
                "name": b.name,
                "broker_id": b.broker_id,
                "symbol": b.symbol,
                "market_type": b.market_type,
                "lower_price": str(b.lower_price),
                "upper_price": str(b.upper_price),
                "grid_count": b.grid_count,
                "investment_usd": str(b.investment_usd),
                "is_active": b.is_active,
                "status": b.status,
                "orders_placed": b.orders_placed,
                "orders_filled": b.orders_filled,
                "realized_pnl": str(b.realized_pnl),
                "last_run_at": b.last_run_at.isoformat() if b.last_run_at else None,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in bots
        ]
    finally:
        session.close()


@router.post("/grid")
def create_grid_bot(req: GridBotCreate, user=Depends(get_current_user)):
    """Create a new grid bot."""
    if req.lower_price >= req.upper_price:
        raise HTTPException(400, "lower_price debe ser menor que upper_price")
    if req.grid_count < 2:
        raise HTTPException(400, "grid_count debe ser >= 2")
    if req.investment_usd <= 0:
        raise HTTPException(400, "investment_usd debe ser > 0")

    session = SessionLocal()
    try:
        bot = GridBot(
            user_id=user.id,
            name=req.name,
            broker_id=req.broker_id,
            symbol=req.symbol.upper(),
            market_type=req.market_type,
            lower_price=Decimal(str(req.lower_price)),
            upper_price=Decimal(str(req.upper_price)),
            grid_count=req.grid_count,
            investment_usd=Decimal(str(req.investment_usd)),
            is_active=False,
            status="stopped",
        )
        session.add(bot)
        session.commit()
        return {"id": bot.id, "status": "created", "name": bot.name}
    finally:
        session.close()


@router.delete("/grid/{bot_id}")
def delete_grid_bot(bot_id: int, user=Depends(get_current_user)):
    """Delete a grid bot."""
    session = SessionLocal()
    try:
        bot = session.query(GridBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Grid bot no encontrado")
        if bot.is_active:
            raise HTTPException(400, "Detén el bot antes de eliminarlo")
        session.delete(bot)
        session.commit()
        return {"status": "deleted", "id": bot_id}
    finally:
        session.close()


@router.post("/grid/{bot_id}/start")
def start_grid_bot(bot_id: int, user=Depends(get_current_user)):
    """Start a grid bot."""
    session = SessionLocal()
    try:
        bot = session.query(GridBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Grid bot no encontrado")
        if bot.is_active:
            return {"status": "already_running", "id": bot_id}

        bot.is_active = True
        bot.status = "running"
        bot.grid_state = {}  # Reset state for fresh start
        session.commit()

        # Ensure scheduler is running
        from app.services.bot_scheduler import get_bot_scheduler
        scheduler = get_bot_scheduler()
        if not scheduler.is_running:
            scheduler.start()

        return {"status": "started", "id": bot_id, "name": bot.name}
    finally:
        session.close()


@router.post("/grid/{bot_id}/stop")
def stop_grid_bot(bot_id: int, user=Depends(get_current_user)):
    """Stop a grid bot."""
    session = SessionLocal()
    try:
        bot = session.query(GridBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Grid bot no encontrado")

        from app.services.grid_engine import GridEngine
        from app.api.helpers import get_shared_broker
        broker = get_shared_broker()
        engine = GridEngine(broker, bot)
        result = engine.stop_grid()
        session.commit()

        return {"status": "stopped", "id": bot_id, "cancelled_orders": result.get("cancelled", 0)}
    finally:
        session.close()


@router.get("/grid/{bot_id}/status")
def grid_bot_status(bot_id: int, user=Depends(get_current_user)):
    """Get detailed status of a grid bot."""
    session = SessionLocal()
    try:
        bot = session.query(GridBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Grid bot no encontrado")

        from app.services.grid_engine import GridEngine
        from app.api.helpers import get_shared_broker
        broker = get_shared_broker()
        engine = GridEngine(broker, bot)
        return engine.get_status()
    finally:
        session.close()


# ─── DCA Bot endpoints ───

@router.get("/dca")
def list_dca_bots(user=Depends(get_current_user)):
    """List all DCA bots for the user."""
    session = SessionLocal()
    try:
        bots = session.query(DCABot).filter_by(user_id=user.id).order_by(DCABot.created_at.desc()).all()
        return [
            {
                "id": b.id,
                "name": b.name,
                "broker_id": b.broker_id,
                "symbol": b.symbol,
                "market_type": b.market_type,
                "buy_amount_usd": str(b.buy_amount_usd),
                "interval_minutes": b.interval_minutes,
                "max_buys": b.max_buys,
                "take_profit_pct": str(b.take_profit_pct),
                "is_active": b.is_active,
                "status": b.status,
                "buys_executed": b.buys_executed,
                "total_invested": str(b.total_invested),
                "total_quantity": str(b.total_quantity),
                "avg_entry_price": str(b.avg_entry_price),
                "realized_pnl": str(b.realized_pnl),
                "last_buy_at": b.last_buy_at.isoformat() if b.last_buy_at else None,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in bots
        ]
    finally:
        session.close()


@router.post("/dca")
def create_dca_bot(req: DCABotCreate, user=Depends(get_current_user)):
    """Create a new DCA bot."""
    if req.buy_amount_usd <= 0:
        raise HTTPException(400, "buy_amount_usd debe ser > 0")
    if req.interval_minutes < 1:
        raise HTTPException(400, "interval_minutes debe ser >= 1")

    session = SessionLocal()
    try:
        bot = DCABot(
            user_id=user.id,
            name=req.name,
            broker_id=req.broker_id,
            symbol=req.symbol.upper(),
            market_type=req.market_type,
            buy_amount_usd=Decimal(str(req.buy_amount_usd)),
            interval_minutes=req.interval_minutes,
            max_buys=req.max_buys,
            take_profit_pct=Decimal(str(req.take_profit_pct)),
            is_active=False,
            status="stopped",
        )
        session.add(bot)
        session.commit()
        return {"id": bot.id, "status": "created", "name": bot.name}
    finally:
        session.close()


@router.delete("/dca/{bot_id}")
def delete_dca_bot(bot_id: int, user=Depends(get_current_user)):
    """Delete a DCA bot."""
    session = SessionLocal()
    try:
        bot = session.query(DCABot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "DCA bot no encontrado")
        if bot.is_active:
            raise HTTPException(400, "Detén el bot antes de eliminarlo")
        session.delete(bot)
        session.commit()
        return {"status": "deleted", "id": bot_id}
    finally:
        session.close()


@router.post("/dca/{bot_id}/start")
def start_dca_bot(bot_id: int, user=Depends(get_current_user)):
    """Start a DCA bot."""
    session = SessionLocal()
    try:
        bot = session.query(DCABot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "DCA bot no encontrado")
        if bot.is_active:
            return {"status": "already_running", "id": bot_id}

        bot.is_active = True
        bot.status = "running"
        session.commit()

        from app.services.bot_scheduler import get_bot_scheduler
        scheduler = get_bot_scheduler()
        if not scheduler.is_running:
            scheduler.start()

        return {"status": "started", "id": bot_id, "name": bot.name}
    finally:
        session.close()


@router.post("/dca/{bot_id}/stop")
def stop_dca_bot(bot_id: int, user=Depends(get_current_user)):
    """Stop a DCA bot."""
    session = SessionLocal()
    try:
        bot = session.query(DCABot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "DCA bot no encontrado")
        bot.is_active = False
        bot.status = "stopped"
        session.commit()
        return {"status": "stopped", "id": bot_id}
    finally:
        session.close()


@router.get("/dca/{bot_id}/status")
def dca_bot_status(bot_id: int, user=Depends(get_current_user)):
    """Get detailed status of a DCA bot."""
    session = SessionLocal()
    try:
        bot = session.query(DCABot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "DCA bot no encontrado")

        from app.services.dca_engine import DCAEngine
        from app.api.helpers import get_shared_broker
        broker = get_shared_broker()
        engine = DCAEngine(broker, bot)
        return engine.get_status()
    finally:
        session.close()


# ─── Scalp Bot endpoints ───

@router.get("/scalp")
def list_scalp_bots(user=Depends(get_current_user)):
    session = SessionLocal()
    try:
        bots = session.query(ScalpBot).filter_by(user_id=user.id).order_by(ScalpBot.created_at.desc()).all()
        return [_scalp_to_dict(b) for b in bots]
    finally:
        session.close()


@router.post("/scalp")
def create_scalp_bot(req: ScalpBotCreate, user=Depends(get_current_user)):
    if req.max_capital_usd <= 0:
        raise HTTPException(400, "max_capital_usd debe ser > 0")
    if req.leverage < 1 or req.leverage > 10:
        raise HTTPException(400, "leverage debe estar entre 1 y 10")
    if req.tp_pct <= 0 or req.sl_pct <= 0:
        raise HTTPException(400, "tp_pct y sl_pct deben ser > 0")

    session = SessionLocal()
    try:
        bot = ScalpBot(
            user_id=user.id,
            name=req.name,
            broker_id=req.broker_id,
            max_capital_usd=Decimal(str(req.max_capital_usd)),
            risk_per_trade_pct=Decimal(str(req.risk_per_trade_pct)),
            leverage=req.leverage,
            tp_pct=Decimal(str(req.tp_pct)),
            sl_pct=Decimal(str(req.sl_pct)),
            max_daily_loss_usd=Decimal(str(req.max_daily_loss_usd)),
            min_atr_pct=Decimal(str(req.min_atr_pct)),
            max_hold_minutes=req.max_hold_minutes,
            ai_refresh_sec=req.ai_refresh_sec,
            use_ai_filter=req.use_ai_filter,
            is_active=False,
            status="stopped",
        )
        session.add(bot)
        session.commit()
        return {"id": bot.id, "status": "created", "name": bot.name}
    finally:
        session.close()


@router.delete("/scalp/{bot_id}")
def delete_scalp_bot(bot_id: int, user=Depends(get_current_user)):
    session = SessionLocal()
    try:
        bot = session.query(ScalpBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Scalp bot no encontrado")
        if bot.is_active:
            raise HTTPException(400, "Detén el bot antes de eliminarlo")
        session.query(ScalpBotLog).filter_by(bot_id=bot_id).delete()
        session.delete(bot)
        session.commit()
        return {"status": "deleted", "id": bot_id}
    finally:
        session.close()


@router.post("/scalp/{bot_id}/start")
def start_scalp_bot(bot_id: int, user=Depends(get_current_user)):
    session = SessionLocal()
    try:
        bot = session.query(ScalpBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Scalp bot no encontrado")
        bot.is_active = True
        bot.status = "running"
        bot.last_heartbeat_at = datetime.now(tz=UTC)
        session.commit()

        from app.services.bot_scheduler import get_bot_scheduler
        scheduler = get_bot_scheduler()
        if not scheduler.is_running:
            scheduler.start()

        return {"status": "started", "id": bot_id, "name": bot.name}
    finally:
        session.close()


@router.post("/scalp/{bot_id}/stop")
def stop_scalp_bot(bot_id: int, user=Depends(get_current_user)):
    session = SessionLocal()
    try:
        bot = session.query(ScalpBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Scalp bot no encontrado")
        bot.is_active = False
        bot.status = "stopped"
        session.commit()
        return {"status": "stopped", "id": bot_id}
    finally:
        session.close()


@router.post("/scalp/{bot_id}/heartbeat")
def scalp_heartbeat(bot_id: int, user=Depends(get_current_user)):
    session = SessionLocal()
    try:
        bot = session.query(ScalpBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Scalp bot no encontrado")
        bot.last_heartbeat_at = datetime.now(tz=UTC)
        session.commit()
        return {"ok": True, "status": bot.status}
    finally:
        session.close()


@router.get("/scalp/{bot_id}/logs")
def scalp_logs(bot_id: int, since_id: int = 0, limit: int = 100, user=Depends(get_current_user)):
    session = SessionLocal()
    try:
        bot = session.query(ScalpBot).filter_by(id=bot_id, user_id=user.id).first()
        if not bot:
            raise HTTPException(404, "Scalp bot no encontrado")
        q = session.query(ScalpBotLog).filter(ScalpBotLog.bot_id == bot_id)
        if since_id:
            q = q.filter(ScalpBotLog.id > since_id)
        logs = q.order_by(ScalpBotLog.id.desc()).limit(min(limit, 200)).all()
        logs = list(reversed(logs))
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "level": e.level,
                "event": e.event,
                "symbol": e.symbol,
                "side": e.side,
                "price": str(e.price) if e.price is not None else None,
                "quantity": str(e.quantity) if e.quantity is not None else None,
                "pnl": str(e.pnl) if e.pnl is not None else None,
                "message": e.message,
            }
            for e in logs
        ]
    finally:
        session.close()


# ─── Scheduler status ───

@router.get("/scheduler/status")
def scheduler_status(user=Depends(get_current_user)):
    """Get the bot scheduler status."""
    from app.services.bot_scheduler import get_bot_scheduler
    scheduler = get_bot_scheduler()
    return scheduler.get_status()


@router.post("/scheduler/start")
def scheduler_start(user=Depends(get_current_user)):
    """Start the bot scheduler."""
    from app.services.bot_scheduler import get_bot_scheduler
    scheduler = get_bot_scheduler()
    if not scheduler.is_running:
        scheduler.start()
    return {"status": "running", "is_running": scheduler.is_running}


@router.post("/scheduler/stop")
def scheduler_stop(user=Depends(get_current_user)):
    """Stop the bot scheduler."""
    from app.services.bot_scheduler import get_bot_scheduler
    scheduler = get_bot_scheduler()
    if scheduler.is_running:
        scheduler.stop()
    return {"status": "stopped", "is_running": scheduler.is_running}


# ─── Symbols endpoint (CCXT) ───

@router.get("/symbols")
def list_trading_symbols(
    quote: str = "USDT",
    limit: int = 200,
    user=Depends(get_current_user),
) -> dict:
    """List available trading symbols from CCXT (Binance by default).

    Returns symbols filtered by quote asset (USDT, BTC, ETH, etc.)
    sorted by volume. Uses CCXT load_markets() + fetch_tickers().
    """
    import logging
    log = logging.getLogger(__name__)

    try:
        import ccxt

        # Use Binance public API (no keys needed for market data)
        exchange = ccxt.binance({"enableRateLimit": True})

        # Load markets
        markets = exchange.load_markets()

        # Filter: spot, active, matching quote asset
        symbols = []
        for sym, market in markets.items():
            if not market.get("active", True):
                continue
            if market.get("type") != "spot":
                continue
            if market.get("quote") != quote.upper():
                continue
            symbols.append({
                "symbol": sym,
                "base": market.get("base", ""),
                "quote": market.get("quote", ""),
            })

        # Try to fetch tickers for volume sorting
        try:
            tickers = exchange.fetch_tickers()
            for s in symbols:
                t = tickers.get(s["symbol"])
                if t:
                    s["volume"] = float(t.get("quoteVolume", 0))
                    s["last_price"] = float(t.get("last", 0))
                    s["change_pct"] = float(t.get("percentage", 0))
                else:
                    s["volume"] = 0
                    s["last_price"] = 0
                    s["change_pct"] = 0
            # Sort by volume descending
            symbols.sort(key=lambda x: x.get("volume", 0), reverse=True)
        except Exception as exc:
            log.warning(f"Could not fetch tickers: {exc}")
            # Sort alphabetically as fallback
            symbols.sort(key=lambda x: x["symbol"])

        # Limit results
        symbols = symbols[:limit]

        # Also return available quote assets
        quote_assets = sorted(set(
            m.get("quote", "") for m in markets.values()
            if m.get("active", True) and m.get("type") == "spot" and m.get("quote")
        ))

        return {
            "status": "ok",
            "quote": quote.upper(),
            "symbols": symbols,
            "total": len(symbols),
            "quote_assets": quote_assets,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "symbols": []}
