"""Historical Data Service — caches klines in DB for long-period backtesting.

Binance API limits klines to 1000 per request. For backtesting with years
of data, we need to download in batches and cache in the market_bars table.

Supports: 1m, 5m, 15m, 1h, 4h, 1d, 1w timeframes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.brokers.models import denormalize_symbol, normalize_symbol
from app.config import get_settings
from app.services.market_data_service import get_market_data_service

logger = logging.getLogger(__name__)

# Binance kline intervals and their approximate durations in minutes
INTERVAL_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}

# Max candles per Binance request
BATCH_SIZE = 1000


class HistoricalDataService:
    """Downloads and caches historical klines in the database."""

    def fetch_and_cache(
        self,
        symbol: str,
        timeframe: str = "1h",
        days: int = 365,
    ) -> dict[str, Any]:
        """Download klines from Binance in batches and cache in DB.

        Args:
            symbol: Trading symbol (e.g. "BTCUSDT")
            timeframe: Kline interval (1m, 5m, 15m, 1h, 4h, 1d, 1w)
            days: Number of days of history to download

        Returns:
            {status, downloaded, cached, gaps}
        """
        from app.database.models.market_bar import MarketBar
        from app.database.session import SessionLocal

        canonical = normalize_symbol(symbol)
        native = denormalize_symbol(canonical, get_settings().DEFAULT_BROKER_ID)
        base_url = get_market_data_service()._get_public_base_url()

        # Calculate time range
        end_time = datetime.now(tz=UTC)
        start_time = end_time - timedelta(days=days)

        downloaded = 0
        cached = 0
        gaps = 0

        db = SessionLocal()
        try:
            # Check what's already cached
            existing = db.query(MarketBar).filter(
                MarketBar.symbol == canonical,
                MarketBar.timeframe == timeframe,
                MarketBar.timestamp >= start_time,
            ).count()

            if existing > 0:
                cached = existing

            # Download in batches
            current_start = start_time
            while current_start < end_time:
                try:
                    params = {
                        "symbol": native,
                        "interval": timeframe,
                        "startTime": int(current_start.timestamp() * 1000),
                        "limit": BATCH_SIZE,
                    }
                    resp = httpx.get(
                        f"{base_url}/api/v3/klines",
                        params=params,
                        timeout=30,
                    )
                    if resp.status_code != 200:
                        gaps += 1
                        break

                    klines = resp.json()
                    if not klines:
                        break

                    # Insert into DB (skip duplicates via unique index)
                    for k in klines:
                        try:
                            bar = MarketBar(
                                timestamp=datetime.fromtimestamp(k[0] / 1000, tz=UTC),
                                symbol=canonical,
                                open=Decimal(str(k[1])),
                                high=Decimal(str(k[2])),
                                low=Decimal(str(k[3])),
                                close=Decimal(str(k[4])),
                                volume=Decimal(str(k[5])),
                                timeframe=timeframe,
                                source="binance",
                            )
                            db.add(bar)
                            downloaded += 1
                        except Exception:
                            # Duplicate — skip
                            db.rollback()
                            continue

                    db.commit()

                    # Move to next batch
                    last_open_time = klines[-1][0]
                    current_start = datetime.fromtimestamp(last_open_time / 1000, tz=UTC) + timedelta(minutes=INTERVAL_MINUTES.get(timeframe, 60))

                    if len(klines) < BATCH_SIZE:
                        break

                except Exception as exc:
                    logger.warning("Error fetching batch: %s", exc)
                    gaps += 1
                    break

            return {
                "status": "ok",
                "symbol": canonical,
                "timeframe": timeframe,
                "days_requested": days,
                "downloaded": downloaded,
                "cached": cached,
                "gaps": gaps,
            }
        except Exception as exc:
            db.rollback()
            logger.error("Error in fetch_and_cache: %s", exc)
            return {"status": "error", "error": str(exc)}
        finally:
            db.close()

    def get_cached_klines(
        self,
        symbol: str,
        timeframe: str = "1h",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict]:
        """Read cached klines from DB.

        Returns list of {timestamp, open, high, low, close, volume} dicts.
        """
        from app.database.models.market_bar import MarketBar
        from app.database.session import SessionLocal

        canonical = normalize_symbol(symbol)

        db = SessionLocal()
        try:
            query = db.query(MarketBar).filter(
                MarketBar.symbol == canonical,
                MarketBar.timeframe == timeframe,
            )
            if start:
                query = query.filter(MarketBar.timestamp >= start)
            if end:
                query = query.filter(MarketBar.timestamp <= end)
            query = query.order_by(MarketBar.timestamp)

            bars = query.all()
            return [
                {
                    "timestamp": bar.timestamp.isoformat() if bar.timestamp else None,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
                for bar in bars
            ]
        finally:
            db.close()

    def get_cache_status(self) -> dict[str, Any]:
        """Get cache status — what symbols/timeframes are cached and their date ranges."""
        from app.database.models.market_bar import MarketBar
        from app.database.session import SessionLocal
        from sqlalchemy import func as sql_func

        db = SessionLocal()
        try:
            # Get distinct symbol/timeframe combos with counts and date ranges
            results = db.query(
                MarketBar.symbol,
                MarketBar.timeframe,
                sql_func.count(MarketBar.id).label("count"),
                sql_func.min(MarketBar.timestamp).label("earliest"),
                sql_func.max(MarketBar.timestamp).label("latest"),
            ).group_by(
                MarketBar.symbol,
                MarketBar.timeframe,
            ).all()

            cached = {}
            for row in results:
                key = f"{row.symbol}_{row.timeframe}"
                cached[key] = {
                    "symbol": row.symbol,
                    "timeframe": row.timeframe,
                    "count": row.count,
                    "earliest": row.earliest.isoformat() if row.earliest else None,
                    "latest": row.latest.isoformat() if row.latest else None,
                }

            return {
                "status": "ok",
                "cached": list(cached.values()),
                "total_entries": sum(r["count"] for r in cached.values()),
            }
        finally:
            db.close()

    def clear_cache(self, symbol: str) -> dict:
        """Clear cached data for a symbol."""
        from app.database.models.market_bar import MarketBar
        from app.database.session import SessionLocal

        canonical = normalize_symbol(symbol)
        db = SessionLocal()
        try:
            deleted = db.query(MarketBar).filter(
                MarketBar.symbol == canonical,
            ).delete()
            db.commit()
            return {"status": "ok", "deleted": deleted}
        except Exception as exc:
            db.rollback()
            return {"status": "error", "error": str(exc)}
        finally:
            db.close()

    def ensure_data_available(
        self,
        symbol: str,
        timeframe: str,
        days_needed: int,
    ) -> dict:
        """Check if enough cached data exists; if not, download it.

        Returns:
            {available: bool, cached_count, needed_count, downloaded}
        """
        from app.database.models.market_bar import MarketBar
        from app.database.session import SessionLocal

        canonical = normalize_symbol(symbol)
        minutes_per_candle = INTERVAL_MINUTES.get(timeframe, 60)
        needed_count = (days_needed * 1440) // minutes_per_candle

        db = SessionLocal()
        try:
            cached_count = db.query(MarketBar).filter(
                MarketBar.symbol == canonical,
                MarketBar.timeframe == timeframe,
            ).count()
        finally:
            db.close()

        if cached_count >= needed_count:
            return {"available": True, "cached_count": cached_count, "needed_count": needed_count, "downloaded": 0}

        # Need to download
        result = self.fetch_and_cache(symbol, timeframe, days_needed)
        return {
            "available": result.get("status") == "ok",
            "cached_count": cached_count,
            "needed_count": needed_count,
            "downloaded": result.get("downloaded", 0),
        }


# Singleton
_service: HistoricalDataService | None = None


def get_historical_data_service() -> HistoricalDataService:
    global _service
    if _service is None:
        _service = HistoricalDataService()
    return _service
