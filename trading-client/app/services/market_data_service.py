"""Market data service — centralizes all external market data fetching.

Two categories:
1. Global intelligence APIs (Fear&Greed, CoinGecko, macro calendar) — not broker-specific
2. Broker market data (ticker, klines) — uses BrokerAdapter when available, falls back to public API

This replaces direct httpx.get("https://api.binance.com/...") calls scattered in routers.
All URLs are configurable via Settings.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.brokers.models import Candle, Ticker, normalize_symbol
from app.config import get_settings

logger = logging.getLogger(__name__)


class MarketDataService:
    """Centralized market data access with configurable URLs and broker abstraction."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── Global intelligence APIs (not broker-specific) ──────────────────

    def get_fear_greed(self, limit: int = 30) -> list[dict]:
        """Fear & Greed Index from alternative.me."""
        url = self._settings.FEAR_GREED_API_URL
        try:
            resp = httpx.get(url, params={"limit": limit}, timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as exc:
            logger.warning("Fear&Greed fetch failed: %s", exc)
            return []

    def get_global_crypto_stats(self) -> dict:
        """Global crypto market stats from CoinGecko (dominance, volume, etc.)."""
        url = f"{self._settings.COINGECKO_API_URL}/global"
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json().get("data", {})
        except Exception as exc:
            logger.warning("CoinGecko global fetch failed: %s", exc)
            return {}

    def get_macro_events(self) -> list[dict]:
        """Weekly macro economic calendar from ForexFactory."""
        url = self._settings.MACRO_CALENDAR_URL
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Macro calendar fetch failed: %s", exc)
            return []

    # ── Broker market data (uses adapter when available) ────────────────

    def get_ticker(self, symbol: str, adapter=None) -> Ticker | None:
        """Get ticker for a symbol.

        Uses BrokerAdapter if provided, otherwise falls back to public API.
        Symbol is in canonical format (BTC/USDT).
        """
        if adapter is not None:
            try:
                return adapter.get_ticker(symbol)
            except Exception as exc:
                logger.warning("Adapter get_ticker failed for %s: %s", symbol, exc)

        # Fallback: public API (no auth needed for market data)
        return self._get_ticker_public(symbol)

    def get_tickers(self, symbols: list[str], adapter=None) -> dict[str, Ticker]:
        """Get tickers for multiple symbols. Returns dict of canonical_symbol -> Ticker."""
        result: dict[str, Ticker] = {}
        for sym in symbols:
            ticker = self.get_ticker(sym, adapter)
            if ticker:
                result[sym] = ticker
        return result

    def get_klines(
        self, symbol: str, interval: str, limit: int = 200, adapter=None
    ) -> list[Candle]:
        """Get OHLCV candles for a symbol.

        Uses BrokerAdapter if provided, otherwise falls back to public API.
        """
        if adapter is not None:
            try:
                return adapter.get_klines(symbol, interval, limit)
            except Exception as exc:
                logger.warning("Adapter get_klines failed for %s: %s", symbol, exc)

        return self._get_klines_public(symbol, interval, limit)

    def get_24hr_ticker(self, symbol: str | None = None, adapter=None) -> dict | None:
        """Get 24hr ticker stats (price change, volume, etc.).

        Uses adapter if available, falls back to public API.
        """
        if adapter is not None:
            try:
                ticker = adapter.get_ticker(symbol) if symbol else None
                if ticker:
                    return {
                        "symbol": ticker.symbol,
                        "lastPrice": str(ticker.price),
                        "priceChange": str(ticker.price_change_24h or Decimal("0")),
                        "priceChangePercent": str(ticker.price_change_percent_24h or Decimal("0")),
                        "volume": str(ticker.volume_24h or Decimal("0")),
                    }
            except Exception as exc:
                logger.warning("Adapter 24hr ticker failed for %s: %s", symbol, exc)

        return self._get_24hr_ticker_public(symbol)

    def get_all_tickers(self, adapter=None) -> list[dict]:
        """Get all tickers (for market overview/movers).

        Uses adapter.get_market_movers if available, falls back to public API.
        """
        if adapter is not None:
            try:
                movers = adapter.get_market_movers(limit=100)
                tickers = []
                for item in movers.get("gainers", []) + movers.get("losers", []):
                    tickers.append({
                        "symbol": item.get("symbol", ""),
                        "lastPrice": str(item.get("price", 0)),
                        "priceChangePercent": str(item.get("price_change_percent", 0)),
                        "volume": str(item.get("volume", 0)),
                    })
                return tickers
            except Exception as exc:
                logger.warning("Adapter market movers failed: %s", exc)

        return self._get_all_tickers_public()

    # ── Public API fallbacks (Binance public, no auth) ──────────────────

    def _get_public_base_url(self) -> str:
        return self._settings.PUBLIC_MARKET_DATA_URL

    def _to_native_symbol(self, symbol: str) -> str:
        """Convert canonical symbol to native format for the public API."""
        from app.brokers.models import denormalize_symbol
        broker_id = self._settings.DEFAULT_BROKER_ID
        return denormalize_symbol(symbol, broker_id)

    def _get_ticker_public(self, symbol: str) -> Ticker | None:
        """Get ticker from public API (no auth)."""
        native = self._to_native_symbol(symbol)
        base = self._get_public_base_url()
        try:
            resp = httpx.get(
                f"{base}/api/v3/ticker/price",
                params={"symbol": native},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return Ticker(
                symbol=normalize_symbol(symbol),
                price=Decimal(str(data["price"])),
                timestamp=datetime.now(UTC),
            )
        except Exception as exc:
            logger.warning("Public ticker fetch failed for %s: %s", symbol, exc)
            return None

    def _get_klines_public(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        """Get klines from public API (no auth)."""
        native = self._to_native_symbol(symbol)
        base = self._get_public_base_url()
        try:
            resp = httpx.get(
                f"{base}/api/v3/klines",
                params={"symbol": native, "interval": interval, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()
            candles: list[Candle] = []
            for row in raw:
                candles.append(Candle(
                    timestamp=datetime.fromtimestamp(row[0] / 1000, tz=UTC),
                    open=Decimal(str(row[1])),
                    high=Decimal(str(row[2])),
                    low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])),
                    volume=Decimal(str(row[5])),
                    interval=interval,
                ))
            return candles
        except Exception as exc:
            logger.warning("Public klines fetch failed for %s: %s", symbol, exc)
            return []

    def _get_24hr_ticker_public(self, symbol: str | None) -> dict | None:
        """Get 24hr ticker from public API."""
        base = self._get_public_base_url()
        try:
            params = {}
            if symbol:
                params["symbol"] = self._to_native_symbol(symbol)
            resp = httpx.get(f"{base}/api/v3/ticker/24hr", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Public 24hr ticker fetch failed: %s", exc)
            return None

    def _get_all_tickers_public(self) -> list[dict]:
        """Get all tickers from public API."""
        base = self._get_public_base_url()
        try:
            resp = httpx.get(f"{base}/api/v3/ticker/24hr", timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Public all tickers fetch failed: %s", exc)
            return []


# Singleton
_service: MarketDataService | None = None


def get_market_data_service() -> MarketDataService:
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service
