"""Generic market data provider using CCXT public APIs.

Fetches OHLCV candles and order book from any exchange supported by CCXT.
No API key needed — uses public endpoints only.
"""

from __future__ import annotations

import logging

import ccxt

logger = logging.getLogger(__name__)

_KLINE_INTERVALS = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


class CCXTDataProvider:
    """Fetches market data from any CCXT-supported exchange via public API."""

    def __init__(self, exchange_id: str = "binance") -> None:
        self._exchange_id = exchange_id
        try:
            exchange_class = getattr(ccxt, exchange_id)
            self._exchange = exchange_class({"enableRateLimit": True})
        except Exception as exc:
            logger.warning("CCXT exchange '%s' not available, falling back to binance: %s", exchange_id, exc)
            self._exchange_id = "binance"
            self._exchange = ccxt.binance({"enableRateLimit": True})

    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 300) -> list[dict]:
        """Fetch OHLCV candles from the exchange.

        Returns list of {open, high, low, close, volume, timestamp} dicts.
        """
        interval = _KLINE_INTERVALS.get(timeframe, timeframe)
        # Normalize symbol: BTCUSDT -> BTC/USDT
        ccxt_symbol = self._normalize_symbol(symbol)
        try:
            ohlcv = self._exchange.fetch_ohlcv(ccxt_symbol, timeframe=interval, limit=limit)
            return [
                {
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                    "timestamp": c[0] / 1000,
                }
                for c in ohlcv
            ]
        except Exception as exc:
            logger.warning("CCXT candles fetch failed for %s %s (%s): %s", ccxt_symbol, interval, self._exchange_id, exc)
            return []

    def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Fetch order book from the exchange."""
        ccxt_symbol = self._normalize_symbol(symbol)
        try:
            ob = self._exchange.fetch_order_book(ccxt_symbol, limit=limit)
            bids = [(float(p), float(q)) for p, q in ob.get("bids", [])]
            asks = [(float(p), float(q)) for p, q in ob.get("asks", [])]
            return {
                "bids": bids,
                "asks": asks,
                "spread": (asks[0][0] - bids[0][0]) if bids and asks else None,
                "bid_depth": sum(q for _, q in bids),
                "ask_depth": sum(q for _, q in asks),
            }
        except Exception as exc:
            logger.warning("CCXT order book fetch failed for %s (%s): %s", ccxt_symbol, self._exchange_id, exc)
            return {}

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize a trading symbol to CCXT format.

        BTCUSDT -> BTC/USDT
        ETH/USDT -> ETH/USDT (already normalized)
        """
        s = symbol.upper().strip()
        if "/" in s:
            return s
        # Common quote currencies
        for quote in ("USDT", "USDC", "BTC", "ETH", "BNB", "FDUSD", "TUSD", "EUR", "USD"):
            if s.endswith(quote) and len(s) > len(quote):
                base = s[:-len(quote)]
                return f"{base}/{quote}"
        # If no known quote found, try USDT as default
        return f"{s}/USDT"
