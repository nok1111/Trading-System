"""Lightweight backtesting service — runs without DB dependency.

Fetches historical klines from Binance, runs a strategy, simulates trades
in-memory, and returns equity curve + metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import numpy as np
import pandas as pd

from app.indicators import indicators as ind

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    interval: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float
    equity_curve: list[dict]
    trades: list[dict]
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "interval": self.interval,
            "initial_cash": self.initial_cash,
            "final_equity": round(self.final_equity, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": round(self.annualized_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades": self.total_trades,
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "timestamp": self.timestamp,
        }


def _fetch_klines_df(symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    """Fetch klines from Binance and return as DataFrame."""
    resp = httpx.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    raw = resp.json()
    df = pd.DataFrame(
        raw,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ],
    )
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["open", "high", "low", "close", "volume"]]


def run_backtest(
    symbol: str,
    strategy: str = "trend_momentum",
    interval: str = "1h",
    limit: int = 500,
    initial_cash: float = 10000.0,
) -> BacktestResult:
    """Run a backtest for a symbol using the specified strategy.

    Args:
        symbol: Trading symbol (e.g. "BTCUSDT")
        strategy: Strategy name ("trend_momentum" or "mean_reversion")
        interval: Kline interval
        limit: Number of candles
        initial_cash: Starting capital

    Returns:
        BacktestResult with equity curve, trades, and metrics.
    """
    if strategy == "mean_reversion":
        return _run_mean_reversion(symbol, interval, limit, initial_cash)
    return _run_trend_momentum(symbol, interval, limit, initial_cash)


def _run_trend_momentum(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
) -> BacktestResult:
    """Backtest for TrendMomentum strategy."""
    df = _fetch_klines_df(symbol, interval, limit)

    # Prepare indicators
    close = df["close"]
    ema_fast = ind.ema(close, 9)
    ema_slow = ind.ema(close, 21)
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    # Simulate trades
    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0

    equity_curve: list[dict] = []
    trades: list[dict] = []

    min_bars = 51  # Need at least 50 for EMA50 + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        # Update position tracking
        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)

            # Trailing stop: 2% below peak
            trailing_stop = highest_since_entry * 0.98
            # Hard stop-loss: 3% below entry
            hard_stop = entry_price * 0.97
            # Take-profit: 6% above entry
            take_profit = entry_price * 1.06

            effective_stop = max(trailing_stop, hard_stop)

            if price <= effective_stop or price >= take_profit:
                # Close position
                sell_price = price
                pnl = (sell_price - entry_price) * position_qty
                cash += position_qty * sell_price
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(),
                    "side": "SELL",
                    "quantity": position_qty,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "reason": "take_profit" if price >= take_profit else "stop_loss",
                    "bars_held": bars_in_position,
                })
                position_qty = 0.0
                entry_price = 0.0
                highest_since_entry = 0.0
                bars_in_position = 0

        # Check for entry signal
        if position_qty == 0:
            ema_f = float(ema_fast.iloc[i])
            ema_s = float(ema_slow.iloc[i])
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            vr = float(vol_rel.iloc[i]) if not vol_rel.isna().iloc[i] else 1.0

            # TrendMomentum: EMA9 > EMA21 + RSI < 60 + volume > 1.5x
            if ema_f > ema_s and rsi_val < 60 and vr > 1.0:
                # Calculate position size: risk 2% of cash
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * 0.03)
                qty = risk_amount / stop_distance

                if qty > 0 and cash > qty * price:
                    entry_price = price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= qty * price
                    trades.append({
                        "entry_time": idx.isoformat(),
                        "exit_time": "",
                        "side": "BUY",
                        "quantity": qty,
                        "entry_price": entry_price,
                        "exit_price": 0,
                        "pnl": 0,
                        "pnl_pct": 0,
                        "reason": "ema_cross_rsi_volume",
                        "bars_held": 0,
                    })

        # Record equity
        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({
            "time": idx.isoformat(),
            "equity": round(equity, 2),
            "price": round(price, 6),
        })

    # Close any remaining position at final price
    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        pnl = (final_price - entry_price) * position_qty
        cash += position_qty * final_price
        trades.append({
            "entry_time": entry_time.isoformat() if entry_time else "",
            "exit_time": df.index[-1].isoformat(),
            "side": "SELL",
            "quantity": position_qty,
            "entry_price": entry_price,
            "exit_price": final_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "reason": "backtest_end",
            "bars_held": bars_in_position,
        })
        position_qty = 0.0

    return _calculate_metrics(
        symbol=symbol,
        strategy="trend_momentum",
        interval=interval,
        initial_cash=initial_cash,
        equity_curve=equity_curve,
        trades=trades,
    )


def _run_mean_reversion(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
) -> BacktestResult:
    """Backtest for MeanReversion strategy (RSI + Bollinger Bands)."""
    df = _fetch_klines_df(symbol, interval, limit)

    # Prepare indicators
    close = df["close"]
    bb = ind.bollinger_bands(close, 20, 2.0)
    bb_upper = bb["upper"]
    bb_middle = bb["middle"]
    bb_lower = bb["lower"]
    bb_width = (bb["upper"] - bb["lower"]) / bb["middle"].replace(0, np.nan)
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    # Strategy params
    rsi_oversold = 30.0
    rsi_overbought = 70.0
    stop_loss_pct = 0.025  # 2.5%
    take_profit_pct = 0.04  # 4%
    max_hold = 24
    trailing_pct = 0.015  # 1.5%

    # Simulate trades
    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0

    equity_curve: list[dict] = []
    trades: list[dict] = []

    min_bars = 21  # BB(20) + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        # Update position tracking
        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)

            # Exit conditions
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            bb_mid = float(bb_middle.iloc[i]) if not bb_middle.isna().iloc[i] else price
            bb_up = float(bb_upper.iloc[i]) if not bb_upper.isna().iloc[i] else price * 1.02

            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            if price <= effective_stop:
                exit_reason = "stop_loss" if price <= hard_stop else "trailing_stop"
            elif price >= take_profit:
                exit_reason = "take_profit"
            elif rsi_val > rsi_overbought:
                exit_reason = "rsi_overbought"
            elif price >= bb_mid:
                exit_reason = "reverted_to_mean"
            elif bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                pnl = (price - entry_price) * position_qty
                cash += position_qty * price
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(),
                    "side": "SELL",
                    "quantity": position_qty,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "reason": exit_reason,
                    "bars_held": bars_in_position,
                })
                position_qty = 0.0
                entry_price = 0.0
                highest_since_entry = 0.0
                bars_in_position = 0

        # Check for entry signal
        if position_qty == 0:
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            bb_low = float(bb_lower.iloc[i]) if not bb_lower.isna().iloc[i] else price
            bb_mid = float(bb_middle.iloc[i]) if not bb_middle.isna().iloc[i] else price
            bw = float(bb_width.iloc[i]) if not bb_width.isna().iloc[i] else 0
            vr = float(vol_rel.iloc[i]) if not vol_rel.isna().iloc[i] else 1.0

            # Entry: RSI oversold + price at/below lower band + volume + band width
            if rsi_val < rsi_oversold and price <= bb_low and vr > 1.0 and bw > 0.02:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance

                if qty > 0 and cash > qty * price:
                    entry_price = price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= qty * price
                    trades.append({
                        "entry_time": idx.isoformat(),
                        "exit_time": "",
                        "side": "BUY",
                        "quantity": qty,
                        "entry_price": entry_price,
                        "exit_price": 0,
                        "pnl": 0,
                        "pnl_pct": 0,
                        "reason": "rsi_oversold_bb_lower",
                        "bars_held": 0,
                    })

        # Record equity
        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({
            "time": idx.isoformat(),
            "equity": round(equity, 2),
            "price": round(price, 6),
        })

    # Close any remaining position at final price
    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        pnl = (final_price - entry_price) * position_qty
        cash += position_qty * final_price
        trades.append({
            "entry_time": entry_time.isoformat() if entry_time else "",
            "exit_time": df.index[-1].isoformat(),
            "side": "SELL",
            "quantity": position_qty,
            "entry_price": entry_price,
            "exit_price": final_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "reason": "backtest_end",
            "bars_held": bars_in_position,
        })
        position_qty = 0.0

    # Calculate metrics (shared logic)
    return _calculate_metrics(
        symbol=symbol,
        strategy="mean_reversion",
        interval=interval,
        initial_cash=initial_cash,
        equity_curve=equity_curve,
        trades=trades,
    )


def _calculate_metrics(
    symbol: str,
    strategy: str,
    interval: str,
    initial_cash: float,
    equity_curve: list[dict],
    trades: list[dict],
) -> BacktestResult:
    """Calculate backtest metrics from equity curve and trades."""
    equity_series = pd.Series([e["equity"] for e in equity_curve])
    final_equity = float(equity_series.iloc[-1]) if len(equity_series) > 0 else initial_cash
    total_return_pct = (final_equity - initial_cash) / initial_cash * 100

    n_bars = len(equity_curve)
    bars_per_year = {"1m": 525600, "5m": 105120, "15m": 35040, "1h": 8760, "4h": 2190, "1d": 365}
    bpy = bars_per_year.get(interval, 8760)
    n_days = max(n_bars / bpy * 365, 1)
    annualized = ((final_equity / initial_cash) ** (365.0 / n_days) - 1) * 100 if final_equity > 0 else 0

    returns = equity_series.pct_change().dropna()
    sharpe = float(returns.mean() / returns.std() * np.sqrt(bpy)) if len(returns) > 1 and returns.std() != 0 else 0.0

    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max
    max_dd = float(drawdown.min()) * 100 if len(drawdown) > 0 else 0.0

    sell_trades = [t for t in trades if t["side"] == "SELL" and t["pnl"] != 0]
    total_closed = len(sell_trades)
    wins = sum(1 for t in sell_trades if t["pnl"] > 0)
    win_rate = wins / total_closed if total_closed else 0.0

    gross_profit = sum(t["pnl"] for t in sell_trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in sell_trades if t["pnl"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    avg_trade = sum(t["pnl"] for t in sell_trades) / total_closed if total_closed else 0.0

    return BacktestResult(
        symbol=symbol.upper(),
        strategy=strategy,
        interval=interval,
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        annualized_return_pct=annualized,
        sharpe_ratio=sharpe,
        max_drawdown_pct=max_dd,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_closed,
        avg_trade_pnl=avg_trade,
        equity_curve=equity_curve,
        trades=trades,
        timestamp=datetime.now(UTC).isoformat(),
    )
