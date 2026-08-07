"""API endpoints para Grid y DCA bots — CRUD + start/stop + status."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import get_current_user
from app.database.session import SessionLocal
from app.database.models.grid_bot import DCABot, GridBot

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
