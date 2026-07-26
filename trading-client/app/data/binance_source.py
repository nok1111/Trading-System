"""Adaptador de datos de mercado para Binance usando la API pública REST."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pandas as pd

from app.data.data_source import DataSource, DataSourceError

_BINANCE_BASE_URL = "https://api.binance.com"
_KLINES_ENDPOINT = "/api/v3/klines"
_TICKER_24HR_ENDPOINT = "/api/v3/ticker/24hr"
_FUTURES_BASE_URL = "https://fapi.binance.com"
_FUTURES_TICKER_ENDPOINT = "/fapi/v1/ticker/24hr"

_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1wk": "1w",
    "1mo": "1M",
}

_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,
}


class BinanceDataSource(DataSource):
    """Adaptador para descargar velas OHLCV desde la API pública de Binance.

    No requiere autenticación para datos históricos (klines).
    """

    def __init__(
        self,
        base_url: str = _BINANCE_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "binance"

    def fetch_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = "1d",
    ) -> pd.DataFrame:
        interval = self._timeframe_to_interval(timeframe)
        start_ms = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp() * 1000)
        end_ms = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp() * 1000)

        all_rows: list[list[Any]] = []
        current_start = start_ms

        while current_start < end_ms:
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ms,
                "limit": 1000,
            }
            try:
                resp = httpx.get(
                    f"{self._base_url}{_KLINES_ENDPOINT}",
                    params=params,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise DataSourceError(
                    f"Error al consultar klines de Binance para {symbol}: {exc}"
                ) from exc

            data = resp.json()
            if not data:
                break

            all_rows.extend(data)

            last_open_time = data[-1][0]
            interval_ms = _INTERVAL_MS.get(interval, 86_400_000)
            current_start = last_open_time + interval_ms

            if len(data) < 1000:
                break

        if not all_rows:
            raise DataSourceError(
                f"Binance no devolvió datos para {symbol} entre {start} y {end} ({timeframe})"
            )

        df = self._parse_klines(all_rows)
        return df

    @staticmethod
    def _parse_klines(rows: list[list[Any]]) -> pd.DataFrame:
        timestamps = [
            datetime.fromtimestamp(row[0] / 1000, tz=UTC) for row in rows
        ]
        df = pd.DataFrame(
            {
                "open": [float(row[1]) for row in rows],
                "high": [float(row[2]) for row in rows],
                "low": [float(row[3]) for row in rows],
                "close": [float(row[4]) for row in rows],
                "volume": [float(row[5]) for row in rows],
            },
            index=pd.DatetimeIndex(timestamps, name="timestamp"),
        )
        return df

    @staticmethod
    def _timeframe_to_interval(timeframe: str) -> str:
        if timeframe not in _TIMEFRAME_MAP:
            raise DataSourceError(f"Timeframe no soportado por Binance: {timeframe}")
        return _TIMEFRAME_MAP[timeframe]

    def get_top_movers(
        self,
        market: str = "spot",
        limit: int = 20,
        quote: str = "USDT",
    ) -> list[dict]:
        """Obtiene los principales ganadores y perdedores de 24h.

        Args:
            market: 'spot' para mercado spot, 'futures' para futuros USD.
            limit: Número de top gainers y top losers a retornar.
            quote: Quote asset para filtrar (ej: USDT, BUSD).

        Returns:
            dict con 'gainers' y 'losers', cada uno una lista de dicts con
            symbol, price, price_change_percent, volume.
        """
        if market == "futures":
            url = f"{_FUTURES_BASE_URL}{_FUTURES_TICKER_ENDPOINT}"
        else:
            url = f"{self._base_url}{_TICKER_24HR_ENDPOINT}"

        try:
            resp = httpx.get(url, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DataSourceError(f"Error al consultar ticker 24h de Binance: {exc}") from exc

        data = resp.json()
        tickers = []
        for item in data:
            symbol = item.get("symbol", "")
            if not symbol.endswith(quote):
                continue
            tickers.append({
                "symbol": symbol,
                "price": float(item.get("lastPrice", 0)),
                "price_change_percent": float(item.get("priceChangePercent", 0)),
                "volume": float(item.get("quoteVolume", 0)),
            })

        tickers.sort(key=lambda x: x["price_change_percent"], reverse=True)
        gainers = tickers[:limit]
        losers = list(reversed(tickers[-limit:]))
        return {"gainers": gainers, "losers": losers}
