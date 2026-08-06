"""Market data endpoints (prices, movers, smart money)."""

from fastapi import APIRouter, HTTPException, Query

from app.data.price_stream import get_price_stream

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/prices/live")
def live_prices() -> dict:
    """Precios en tiempo real desde WebSocket de Binance."""
    stream = get_price_stream()
    if not stream:
        return {"connected": False, "prices": {}, "reconnect_count": 0, "last_update_age": -1}
    return {
        "connected": stream.is_connected,
        "prices": {k: str(v) for k, v in stream.get_all_prices().items()},
        "reconnect_count": stream.reconnect_count,
        "last_update_age": round(stream.get_last_update_age(), 1),
    }


@router.get("/prices/live/{symbol}")
def live_price(symbol: str) -> dict:
    """Precio en tiempo real para un símbolo específico."""
    stream = get_price_stream()
    if not stream:
        return {"symbol": symbol.upper(), "price": None, "connected": False}
    price = stream.get_price(symbol)
    return {
        "symbol": symbol.upper(),
        "price": str(price) if price else None,
        "connected": stream.is_connected,
    }


@router.get("/market/movers")
def market_movers(
    market: str = Query("spot", pattern="^(spot|futures)$"),
    limit: int = Query(20, ge=1, le=100),
    quote: str = Query("USDT"),
) -> dict:
    """Top gainers y losers de Binance (spot o futuros USD) en 24h."""
    from app.data.binance_source import BinanceDataSource

    ds = BinanceDataSource()
    try:
        return ds.get_top_movers(market=market, limit=limit, quote=quote)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/smart-money")
def smart_money(
    period: str = Query("7d", pattern="^(24h|3d|7d|30d|90d|1y|all)$"),
    stat_type: str = Query("ROI", pattern="^(ROI|PNL)$"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Top traders del leaderboard de Binance Futures (Smart Money)."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_top_traders(period=period, stat_type=stat_type, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/smart-money/{encrypted_uid}/positions")
def smart_money_positions(encrypted_uid: str) -> list[dict]:
    """Posiciones abiertas de un trader específico del leaderboard."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_trader_positions(encrypted_uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/market/smart-money/{encrypted_uid}/info")
def smart_money_info(encrypted_uid: str) -> dict:
    """Información detallada de un trader del leaderboard."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_trader_info(encrypted_uid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
