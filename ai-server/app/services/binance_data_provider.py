"""Binance data provider for the Market Data Engine.

Fetches OHLCV candles and order book from Binance public API (no key needed).
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_BINANCE_BASE = "https://api.binance.com"
_KLINE_INTERVALS = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


class BinanceDataProvider:
    """Fetches market data from Binance public REST API."""

    def __init__(self, base_url: str = _BINANCE_BASE) -> None:
        self._base_url = base_url.rstrip("/")

    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 300) -> list[dict]:
        """Fetch OHLCV candles from Binance.

        Returns list of {open, high, low, close, volume, timestamp} dicts.
        """
        interval = _KLINE_INTERVALS.get(timeframe, timeframe)
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/klines",
                params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
                timeout=15.0,
            )
            resp.raise_for_status()
            rows = resp.json()
            return [
                {
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                    "volume": float(r[5]),
                    "timestamp": r[0] / 1000,
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("Binance candles fetch failed for %s %s: %s", symbol, interval, exc)
            return []

    def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Fetch order book from Binance."""
        try:
            resp = httpx.get(
                f"{self._base_url}/api/v3/depth",
                params={"symbol": symbol.upper(), "limit": limit},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
            asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
            return {
                "bids": bids,
                "asks": asks,
                "spread": (asks[0][0] - bids[0][0]) if bids and asks else None,
                "bid_depth": sum(q for _, q in bids),
                "ask_depth": sum(q for _, q in asks),
            }
        except Exception as exc:
            logger.warning("Binance order book fetch failed for %s: %s", symbol, exc)
            return {}
