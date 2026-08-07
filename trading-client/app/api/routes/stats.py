"""Stats, risk events, and chart endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.api.routes.trading import DbSession
from app.config import get_settings
from app.database.models import (
    AccountSnapshot,
    Order,
    Position,
    PredictionRecord,
    Signal,
    StrategyRun,
    Trade,
)

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def trading_stats(db: DbSession) -> dict:
    """Estadisticas de performance por periodo: hoy, ayer, semana, todo."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(tz=UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)

    def _period_stats(start: datetime | None) -> dict:
        q = db.query(Trade).filter(Trade.side == "SELL")
        if start is not None:
            q = q.filter(Trade.timestamp >= start)
        trades = q.all()
        pnls = [float(t.realized_pnl) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)
        total_trades = len(pnls)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        avg_win = (sum(wins) / len(wins)) if wins else 0
        avg_loss = (sum(losses) / len(losses)) if losses else 0
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0

        # Count buy trades (entries) in the period
        buy_q = db.query(Trade).filter(Trade.side == "BUY")
        if start is not None:
            buy_q = buy_q.filter(Trade.timestamp >= start)
        entries = buy_q.count()

        # Open positions count
        open_pos = db.query(Position).filter(Position.status == "open").count()

        return {
            "trades_closed": total_trades,
            "entries": entries,
            "open_positions": open_pos,
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "wins": len(wins),
            "losses": len(losses),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
        }

    # Daily PnL series (last 14 days)
    daily_pnl = []
    for i in range(13, -1, -1):
        day_start = (today_start - timedelta(days=i)).replace(tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        day_trades = (
            db.query(Trade)
            .filter(Trade.side == "SELL", Trade.timestamp >= day_start, Trade.timestamp < day_end)
            .all()
        )
        day_total = sum(float(t.realized_pnl) for t in day_trades)
        daily_pnl.append({
            "date": day_start.strftime("%m-%d"),
            "pnl": round(day_total, 2),
            "trades": len(day_trades),
        })

    return {
        "today": _period_stats(today_start),
        "yesterday": _period_stats(yesterday_start),
        "week": _period_stats(week_start),
        "all_time": _period_stats(None),
        "daily_pnl": daily_pnl,
    }


@router.get("/risk-events")
def list_risk_events(
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    """Eventos de riesgo recientes (señales rechazadas y motivos)."""
    from app.database.models.risk_event import RiskEvent
    events = (
        db.query(RiskEvent)
        .order_by(RiskEvent.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "symbol": e.symbol,
            "reason": e.reason,
            "severity": e.severity,
            "signal_type": (e.details or {}).get("signal_type", ""),
            "strategy_name": (e.details or {}).get("strategy_name", ""),
        }
        for e in events
    ]


@router.get("/stats/symbols")
def stats_by_symbol(db: DbSession) -> list[dict]:
    """Estadísticas por símbolo: trades, win rate, PnL, frecuencia."""
    from sqlalchemy import and_, case, func

    rows = (
        db.query(
            Trade.symbol,
            func.count(Trade.id).label("total_trades"),
            func.sum(case((Trade.side == "BUY", 1), else_=0)).label("buys"),
            func.sum(case((Trade.side == "SELL", 1), else_=0)).label("sells"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl > 0), 1), else_=0)).label("wins"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl < 0), 1), else_=0)).label("losses"),
            func.sum(Trade.realized_pnl).label("total_pnl"),
            func.avg(Trade.price).label("avg_price"),
        )
        .group_by(Trade.symbol)
        .order_by(func.count(Trade.id).desc())
        .all()
    )

    result = []
    for r in rows:
        sells = int(r.sells or 0)
        wins = int(r.wins or 0)
        losses = int(r.losses or 0)
        win_rate = (wins / sells * 100) if sells > 0 else 0
        result.append({
            "symbol": r.symbol,
            "total_trades": int(r.total_trades),
            "buys": int(r.buys or 0),
            "sells": sells,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(float(r.total_pnl or 0), 2),
            "avg_price": round(float(r.avg_price or 0), 4),
        })
    return result


@router.get("/stats/simulations")
def stats_simulations(db: DbSession) -> list[dict]:
    """Estadísticas por simulación (strategy run): PnL, trades, win rate, símbolos."""
    from sqlalchemy import case, func

    runs = (
        db.query(StrategyRun)
        .filter(StrategyRun.mode == "paper")
        .order_by(StrategyRun.id.desc())
        .limit(20)
        .all()
    )

    result = []
    for run in runs:
        sell_trades = (
            db.query(Trade)
            .filter(Trade.side == "SELL")
            .all()
        )
        sell_pnls = [float(t.realized_pnl) for t in sell_trades]
        wins = [p for p in sell_pnls if p > 0]
        losses = [p for p in sell_pnls if p < 0]
        total_pnl = sum(sell_pnls)
        win_rate = (len(wins) / len(sell_pnls) * 100) if sell_pnls else 0

        symbols_traded = list(set(t.symbol for t in sell_trades))
        buy_count = (
            db.query(func.count(Trade.id))
            .filter(Trade.side == "BUY")
            .scalar() or 0
        )

        result.append({
            "run_id": run.id,
            "strategy": run.strategy_name,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "total_trades": len(sell_pnls) + int(buy_count),
            "trades_closed": len(sell_pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
            "symbols": symbols_traded,
            "symbol_count": len(symbols_traded),
        })
    return result


@router.get("/stats/by-strategy")
def stats_by_strategy(db: DbSession) -> list[dict]:
    """Estadísticas agrupadas por estrategia: win rate, PnL, trades."""
    from sqlalchemy import and_, case, func

    rows = (
        db.query(
            Signal.strategy_name,
            func.count(Trade.id).label("total_trades"),
            func.sum(case((Trade.side == "BUY", 1), else_=0)).label("buys"),
            func.sum(case((Trade.side == "SELL", 1), else_=0)).label("sells"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl > 0), 1), else_=0)).label("wins"),
            func.sum(case((and_(Trade.side == "SELL", Trade.realized_pnl < 0), 1), else_=0)).label("losses"),
            func.sum(Trade.realized_pnl).label("total_pnl"),
        )
        .join(Order, Trade.order_id == Order.id)
        .join(Signal, Order.signal_id == Signal.id)
        .group_by(Signal.strategy_name)
        .all()
    )

    result = []
    for r in rows:
        sells = int(r.sells or 0)
        wins = int(r.wins or 0)
        losses = int(r.losses or 0)
        win_rate = (wins / sells * 100) if sells > 0 else 0
        pnl = float(r.total_pnl or 0)
        result.append({
            "strategy": r.strategy_name,
            "total_trades": int(r.total_trades or 0),
            "buys": int(r.buys or 0),
            "sells": sells,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(pnl, 2),
            "avg_pnl": round(pnl / sells, 2) if sells > 0 else 0,
        })
    return result


@router.post("/stats/reset")
def reset_stats(db: DbSession, force: bool = Query(False)) -> dict:
    """Elimina todos los trades, orders, signals, positions y snapshots para reiniciar stats.

    En modo live, bloquea el reset si hay posiciones abiertas para evitar
    perder el rastreo de posiciones reales en Binance.
    Usa ?force=true para forzar el reset (ej: posiciones de test atoradas).
    """
    settings = get_settings()
    is_live = settings.TRADING_MODE == "live" and settings.LIVE_TRADING_ENABLED

    if is_live and not force:
        open_count = db.query(Position).filter(Position.status == "open").count()
        if open_count > 0:
            raise HTTPException(
                status_code=403,
                detail=f"No se puede reiniciar stats en modo live con {open_count} posiciones abiertas. "
                       "Cierra todas las posiciones primero, o usa force=true si son posiciones de test.",
            )

    db.query(Trade).delete()
    db.query(Order).delete()
    db.query(Signal).delete()
    db.query(Position).delete()
    db.query(AccountSnapshot).delete()
    db.query(PredictionRecord).delete()
    db.query(StrategyRun).filter(StrategyRun.mode == "paper").delete()
    db.commit()
    return {"status": "ok", "message": "Stats reiniciados" + (" (forzado)" if force and is_live else "")}


@router.get("/charts/position/{symbol}")
def position_chart_data(symbol: str, db: DbSession) -> dict:
    """Datos para graficar una posicion abierta: niveles de entrada, SL, TP y precio live."""
    settings = get_settings()
    pos = db.query(Position).filter_by(symbol=symbol.upper(), status="open").first()
    if pos is None:
        raise HTTPException(status_code=404, detail="No hay posicion abierta para " + symbol)

    # Fetch live price from Binance (spot first, then futures)
    live_price = None
    try:
        import httpx as _httpx
        resp = _httpx.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}",
            timeout=5.0,
        )
        if resp.status_code == 200:
            live_price = float(resp.json()["price"])
        else:
            resp = _httpx.get(
                f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.upper()}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                live_price = float(resp.json()["price"])
    except Exception:
        pass

    # Update position current_price and unrealized_pnl in DB
    if live_price and live_price > 0:
        from decimal import Decimal as Dec
        pos.current_price = Dec(str(live_price))
        pos.unrealized_pnl = (Dec(str(live_price)) - pos.entry_price) * pos.quantity
        db.add(pos)
        db.commit()

    entry = float(pos.entry_price)
    pnl_pct = ((live_price - entry) / entry * 100) if live_price and entry > 0 else 0.0

    return {
        "symbol": symbol.upper(),
        "entry_price": entry,
        "current_price": live_price,
        "stop_loss": float(pos.stop_loss) if pos.stop_loss else None,
        "take_profit": float(pos.take_profit) if pos.take_profit else None,
        "quantity": float(pos.quantity),
        "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        "live_price": live_price,
        "unrealized_pnl": float(pos.unrealized_pnl) if pos.unrealized_pnl else 0.0,
        "pnl_pct": pnl_pct,
        "timeframe": settings.DATA_TIMEFRAME,
    }


@router.get("/portfolio-risk")
def portfolio_risk(db: DbSession) -> dict:
    """Portfolio-level risk assessment: correlation, VaR, exposure limits."""
    import logging as _log

    logger = _log.getLogger(__name__)
    from app.risk.portfolio_risk import assess_portfolio_risk

    # Get open positions
    positions_db = db.query(Position).filter_by(status="open").all()
    if not positions_db:
        return {
            "total_exposure": 0,
            "max_single_position_pct": 0,
            "category_exposure": {},
            "category_limits": {},
            "category_warnings": [],
            "correlation_warnings": [],
            "correlation_matrix": {},
            "avg_correlation": 0,
            "var": None,
            "risk_score": 0,
            "recommendations": ["No hay posiciones abiertas"],
            "positions": [],
        }

    # Fetch live prices for all positions
    import httpx as _httpx

    positions_data: list[dict] = []
    for pos in positions_db:
        live_price = float(pos.current_price or pos.entry_price)
        try:
            resp = _httpx.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={pos.symbol.upper()}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                live_price = float(resp.json()["price"])
        except Exception:
            pass

        value = float(pos.quantity) * live_price
        positions_data.append({
            "symbol": pos.symbol,
            "quantity": float(pos.quantity),
            "entry_price": float(pos.entry_price),
            "current_price": live_price,
            "value": value,
            "unrealized_pnl": float(pos.unrealized_pnl or 0),
        })

    # Calculate portfolio value (sum of position values + cash)
    total_position_value = sum(p["value"] for p in positions_data)
    account = db.query(AccountSnapshot).order_by(AccountSnapshot.timestamp.desc()).first()
    cash = float(account.cash) if account else 0
    portfolio_value = total_position_value + cash

    # Run assessment
    assessment = assess_portfolio_risk(positions_data, portfolio_value)
    result = assessment.to_dict()
    result["positions"] = positions_data
    result["portfolio_value"] = round(portfolio_value, 2)
    result["cash"] = round(cash, 2)
    return result
