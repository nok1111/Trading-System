"""Market data endpoints (prices, movers, smart money)."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.data.price_stream import get_price_stream

logger = logging.getLogger(__name__)

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
    from app.brokers.adapters.binance_adapter import BinanceAdapter
    from app.brokers.models import BrokerCredentials
    from app.config import get_settings

    settings = get_settings()
    creds = BrokerCredentials(
        broker_id="binance",
        api_key=getattr(settings, "BROKER_API_KEY", "") or "",
        api_secret=getattr(settings, "BROKER_API_SECRET", "") or "",
        testnet=getattr(settings, "BINANCE_TESTNET", False),
    )
    adapter = BinanceAdapter(creds)
    try:
        result = adapter.get_market_movers(market=market, limit=limit, quote=quote)
        return {
            "gainers": [
                {
                    "symbol": t["symbol"],
                    "price": float(t["price"]),
                    "price_change_percent": float(t["price_change_percent"]),
                    "volume": float(t["volume"]),
                }
                for t in result["gainers"]
            ],
            "losers": [
                {
                    "symbol": t["symbol"],
                    "price": float(t["price"]),
                    "price_change_percent": float(t["price_change_percent"]),
                    "volume": float(t["volume"]),
                }
                for t in result["losers"]
            ],
        }
    except Exception as exc:
        logger.warning("Market data error: %s", exc)
        raise HTTPException(status_code=502, detail="Error al obtener datos de mercado") from exc


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
        logger.warning("Market data error: %s", exc)
        raise HTTPException(status_code=502, detail="Error al obtener datos de mercado") from exc


@router.get("/market/smart-money/{encrypted_uid}/positions")
def smart_money_positions(encrypted_uid: str) -> list[dict]:
    """Posiciones abiertas de un trader específico del leaderboard."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_trader_positions(encrypted_uid)
    except Exception as exc:
        logger.warning("Market data error: %s", exc)
        raise HTTPException(status_code=502, detail="Error al obtener datos de mercado") from exc


@router.get("/market/smart-money/{encrypted_uid}/info")
def smart_money_info(encrypted_uid: str) -> dict:
    """Información detallada de un trader del leaderboard."""
    from app.data.binance_leaderboard import BinanceLeaderboard

    lb = BinanceLeaderboard()
    try:
        return lb.get_trader_info(encrypted_uid)
    except Exception as exc:
        logger.warning("Market data error: %s", exc)
        raise HTTPException(status_code=502, detail="Error al obtener datos de mercado") from exc


@router.get("/klines/{symbol}")
def get_klines(
    symbol: str,
    interval: str = Query("1m", pattern="^(1m|3m|5m|15m|30m|1h|2h|4h|1d|1w)$"),
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict]:
    """Klines (OHLCV) desde Binance public API — no credentials needed."""
    import httpx

    broker_symbol = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    try:
        resp = httpx.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": broker_symbol, "interval": interval, "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            raise HTTPException(status_code=400, detail=f"Simbolo {symbol} no existe en Binance") from exc
        raise HTTPException(status_code=502, detail=f"Error HTTP {exc.response.status_code}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=504, detail=f"Timeout conectando a Binance: {exc}") from exc

    raw = resp.json()
    from datetime import datetime, UTC
    return [
        {
            "time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in raw
    ]
