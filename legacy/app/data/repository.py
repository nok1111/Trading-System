"""Repositorio de velas OHLCV en base de datos."""

from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.market_bar import MarketBar


class BarRepository:
    """Acceso a MarketBar para leer y escribir velas."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str,
    ) -> pd.DataFrame:
        """Recupera velas de la base de datos en el rango solicitado."""
        stmt = (
            select(MarketBar)
            .where(
                MarketBar.symbol == symbol,
                MarketBar.timeframe == timeframe,
                MarketBar.timestamp >= start,
                MarketBar.timestamp <= end,
            )
            .order_by(MarketBar.timestamp)
        )
        rows = self.session.execute(stmt).scalars().all()
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"]).set_axis(
                pd.DatetimeIndex([], name="timestamp")
            )

        data = {
            "open": [float(r.open) for r in rows],
            "high": [float(r.high) for r in rows],
            "low": [float(r.low) for r in rows],
            "close": [float(r.close) for r in rows],
            "volume": [float(r.volume) for r in rows],
        }
        index = pd.DatetimeIndex([r.timestamp for r in rows], name="timestamp")
        df = pd.DataFrame(data, index=index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        return df

    def upsert_bars(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        source: str,
    ) -> None:
        """Inserta velas nuevas sin duplicar la clave única (timestamp, symbol, timeframe)."""
        if df.empty:
            return
        existing_rows = (
            self.session.execute(
                select(MarketBar.timestamp).where(
                    MarketBar.symbol == symbol,
                    MarketBar.timeframe == timeframe,
                    MarketBar.timestamp.in_(df.index.to_pydatetime().tolist()),
                )
            )
            .scalars()
            .all()
        )

        existing = set()
        for ts in existing_rows:
            ts_obj = pd.Timestamp(ts)
            if ts_obj.tz is None:
                existing.add(ts_obj.tz_localize("UTC"))
            else:
                existing.add(ts_obj.tz_convert("UTC"))

        for timestamp, row in df.iterrows():
            ts = pd.Timestamp(timestamp)
            ts = ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")
            if ts in existing:
                continue
            bar = MarketBar(
                timestamp=timestamp.to_pydatetime(),
                symbol=symbol,
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
                timeframe=timeframe,
                source=source,
            )
            self.session.add(bar)
        self.session.commit()
