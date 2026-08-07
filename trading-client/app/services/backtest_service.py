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
    # New fields
    buy_hold_return_pct: float = 0.0
    total_fees: float = 0.0
    total_slippage_cost: float = 0.0
    net_return_pct: float = 0.0
    alpha_pct: float = 0.0  # strategy return minus buy-and-hold

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
            "buy_hold_return_pct": round(self.buy_hold_return_pct, 2),
            "total_fees": round(self.total_fees, 2),
            "total_slippage_cost": round(self.total_slippage_cost, 2),
            "net_return_pct": round(self.net_return_pct, 2),
            "alpha_pct": round(self.alpha_pct, 2),
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


# ─── Fees & Slippage ──────────────────────────────────────────────────────────

# Binance spot: 0.1% taker fee per trade (0.075% with BNB discount)
DEFAULT_FEE_PCT = 0.001  # 0.1%
# Simulate slippage: buy at slightly above close, sell at slightly below
DEFAULT_SLIPPAGE_PCT = 0.0005  # 0.05%


def _apply_slippage_buy(price: float, slippage_pct: float = DEFAULT_SLIPPAGE_PCT) -> float:
    """Simulate buying at a slightly worse price."""
    return price * (1 + slippage_pct)


def _apply_slippage_sell(price: float, slippage_pct: float = DEFAULT_SLIPPAGE_PCT) -> float:
    """Simulate selling at a slightly worse price."""
    return price * (1 - slippage_pct)


def _calculate_fee(trade_value: float, fee_pct: float = DEFAULT_FEE_PCT) -> float:
    """Calculate exchange fee for a trade."""
    return trade_value * fee_pct


def _calculate_buy_hold(df: pd.DataFrame, initial_cash: float) -> float:
    """Calculate buy-and-hold return percentage.

    Buys at the first close, holds until the last close.
    Returns the return percentage.
    """
    if len(df) < 2:
        return 0.0
    first_price = float(df.iloc[0]["close"])
    last_price = float(df.iloc[-1]["close"])
    # Account for the fee to buy and the fee to sell
    buy_price = first_price * (1 + DEFAULT_FEE_PCT)
    sell_price = last_price * (1 - DEFAULT_FEE_PCT)
    qty = initial_cash / buy_price
    final_value = qty * sell_price
    # Subtract sell fee
    final_value -= final_value * DEFAULT_FEE_PCT
    return (final_value - initial_cash) / initial_cash * 100


def run_backtest(
    symbol: str,
    strategy: str = "trend_momentum",
    interval: str = "1h",
    limit: int = 500,
    initial_cash: float = 10000.0,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
) -> BacktestResult:
    """Run a backtest for a symbol using the specified strategy.

    Args:
        symbol: Trading symbol (e.g. "BTCUSDT")
        strategy: Strategy name ("trend_momentum" or "mean_reversion")
        interval: Kline interval
        limit: Number of candles
        initial_cash: Starting capital
        fee_pct: Exchange fee per trade (default 0.1%)
        slippage_pct: Slippage per trade (default 0.05%)

    Returns:
        BacktestResult with equity curve, trades, and metrics.
    """
    if strategy == "mean_reversion":
        return _run_mean_reversion(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    if strategy == "breakout":
        return _run_breakout(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    if strategy == "grid":
        return _run_grid(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    if strategy == "macd_momentum":
        return _run_macd_momentum(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    if strategy == "bollinger_squeeze":
        return _run_bollinger_squeeze(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    if strategy == "supertrend":
        return _run_supertrend(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    if strategy == "rsi_divergence":
        return _run_rsi_divergence(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)
    return _run_trend_momentum(symbol, interval, limit, initial_cash, fee_pct, slippage_pct)


def _run_trend_momentum(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
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
    entry_price = 0.0  # actual fill price (with slippage)
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0
    total_fees = 0.0
    total_slippage = 0.0

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
                # Close position — apply slippage and fees
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(),
                    "side": "SELL",
                    "quantity": position_qty,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2),
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

                # Apply slippage to buy price
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)

                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee
                    total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({
                        "entry_time": idx.isoformat(),
                        "exit_time": "",
                        "side": "BUY",
                        "quantity": qty,
                        "entry_price": entry_price,
                        "exit_price": 0,
                        "pnl": 0,
                        "pnl_pct": 0,
                        "fee": round(fee, 2),
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
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({
            "entry_time": entry_time.isoformat() if entry_time else "",
            "exit_time": df.index[-1].isoformat(),
            "side": "SELL",
            "quantity": position_qty,
            "entry_price": entry_price,
            "exit_price": sell_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2),
            "reason": "backtest_end",
            "bars_held": bars_in_position,
        })
        position_qty = 0.0

    # Buy-and-hold comparison
    buy_hold_pct = _calculate_buy_hold(df, initial_cash)

    return _calculate_metrics(
        symbol=symbol,
        strategy="trend_momentum",
        interval=interval,
        initial_cash=initial_cash,
        equity_curve=equity_curve,
        trades=trades,
        total_fees=total_fees,
        total_slippage=total_slippage,
        buy_hold_return_pct=buy_hold_pct,
    )


def _run_mean_reversion(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
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
    total_fees = 0.0
    total_slippage = 0.0

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
                # Apply slippage and fees
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(),
                    "side": "SELL",
                    "quantity": position_qty,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2),
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

                # Apply slippage to buy price
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)

                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee
                    total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({
                        "entry_time": idx.isoformat(),
                        "exit_time": "",
                        "side": "BUY",
                        "quantity": qty,
                        "entry_price": entry_price,
                        "exit_price": 0,
                        "pnl": 0,
                        "pnl_pct": 0,
                        "fee": round(fee, 2),
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
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({
            "entry_time": entry_time.isoformat() if entry_time else "",
            "exit_time": df.index[-1].isoformat(),
            "side": "SELL",
            "quantity": position_qty,
            "entry_price": entry_price,
            "exit_price": sell_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2),
            "reason": "backtest_end",
            "bars_held": bars_in_position,
        })
        position_qty = 0.0

    # Buy-and-hold comparison
    buy_hold_pct = _calculate_buy_hold(df, initial_cash)

    return _calculate_metrics(
        symbol=symbol,
        strategy="mean_reversion",
        interval=interval,
        initial_cash=initial_cash,
        equity_curve=equity_curve,
        trades=trades,
        total_fees=total_fees,
        total_slippage=total_slippage,
        buy_hold_return_pct=buy_hold_pct,
    )


def _calculate_metrics(
    symbol: str,
    strategy: str,
    interval: str,
    initial_cash: float,
    equity_curve: list[dict],
    trades: list[dict],
    total_fees: float = 0.0,
    total_slippage: float = 0.0,
    buy_hold_return_pct: float = 0.0,
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

    # Net return already accounts for fees (they were deducted from cash)
    # Alpha = strategy return - buy-and-hold return
    alpha = total_return_pct - buy_hold_return_pct

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
        buy_hold_return_pct=buy_hold_return_pct,
        total_fees=total_fees,
        total_slippage_cost=total_slippage,
        net_return_pct=total_return_pct,  # fees already deducted from equity
        alpha_pct=alpha,
    )


# ─── Breakout Strategy Backtest ───────────────────────────────────────────────


def _run_breakout(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    donchian_period: int = 20,
    volume_threshold: float = 1.5,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.08,
    trailing_pct: float = 0.025,
    max_hold: int = 48,
) -> BacktestResult:
    """Backtest for Breakout strategy (Donchian Channels + volume)."""
    df = _fetch_klines_df(symbol, interval, limit)

    close = df["close"]
    dc = ind.donchian_channels(df, donchian_period)
    dc_upper = dc["upper"]
    dc_middle = dc["middle"]
    dc_lower = dc["lower"]
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0
    total_fees = 0.0
    total_slippage = 0.0

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = donchian_period + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            dc_mid = float(dc_middle.iloc[i]) if not dc_middle.isna().iloc[i] else price

            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            if price <= effective_stop:
                exit_reason = "stop_loss" if price <= hard_stop else "trailing_stop"
            elif price >= take_profit:
                exit_reason = "take_profit"
            elif price < dc_mid:
                exit_reason = "below_channel_mid"
            elif bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(),
                    "side": "SELL",
                    "quantity": position_qty,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2),
                    "reason": exit_reason,
                    "bars_held": bars_in_position,
                })
                position_qty = 0.0
                entry_price = 0.0
                highest_since_entry = 0.0
                bars_in_position = 0

        # Entry: price breaks above previous Donchian upper + volume
        if position_qty == 0:
            prev_upper = float(dc_upper.iloc[i - 1]) if i > 0 and not dc_upper.isna().iloc[i - 1] else 0
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            vr = float(vol_rel.iloc[i]) if not vol_rel.isna().iloc[i] else 1.0

            if price > prev_upper and vr > volume_threshold and rsi_val > 40:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)

                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee
                    total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({
                        "entry_time": idx.isoformat(),
                        "exit_time": "",
                        "side": "BUY",
                        "quantity": qty,
                        "entry_price": entry_price,
                        "exit_price": 0,
                        "pnl": 0,
                        "pnl_pct": 0,
                        "fee": round(fee, 2),
                        "reason": "donchian_breakout",
                        "bars_held": 0,
                    })

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({
            "entry_time": entry_time.isoformat() if entry_time else "",
            "exit_time": df.index[-1].isoformat(),
            "side": "SELL",
            "quantity": position_qty,
            "entry_price": entry_price,
            "exit_price": sell_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2),
            "reason": "backtest_end",
            "bars_held": bars_in_position,
        })

    buy_hold_pct = _calculate_buy_hold(df, initial_cash)
    return _calculate_metrics(
        symbol=symbol, strategy="breakout", interval=interval,
        initial_cash=initial_cash, equity_curve=equity_curve, trades=trades,
        total_fees=total_fees, total_slippage=total_slippage, buy_hold_return_pct=buy_hold_pct,
    )


# ─── Grid Strategy Backtest ───────────────────────────────────────────────────


def _run_grid(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    atr_multiplier: float = 2.0,
    grid_levels: int = 5,
    stop_loss_pct: float = 0.04,
    max_hold: int = 72,
) -> BacktestResult:
    """Backtest for Grid strategy (range trading with ATR-based levels)."""
    df = _fetch_klines_df(symbol, interval, limit)

    close = df["close"]
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    entry_time = None
    bars_in_position = 0
    total_fees = 0.0
    total_slippage = 0.0
    # Track grid center — recalculated when no position
    grid_center = 0.0
    grid_spacing = 0.0

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = 15

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        # Recalculate grid when not in position — use previous candle as center
        if position_qty == 0 and i > 0:
            atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
            grid_center = float(df.iloc[i - 1]["close"])
            grid_spacing = (atr_val * atr_multiplier) / grid_levels

        if position_qty > 0:
            bars_in_position += 1

            # Grid sell level = entry + spacing
            sell_level = entry_price + grid_spacing
            hard_stop = entry_price * (1 - stop_loss_pct)

            exit_reason = None
            if price >= sell_level:
                exit_reason = "grid_sell_level"
            elif price <= hard_stop:
                exit_reason = "stop_loss"
            elif bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(),
                    "side": "SELL",
                    "quantity": position_qty,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2),
                    "reason": exit_reason,
                    "bars_held": bars_in_position,
                })
                position_qty = 0.0
                entry_price = 0.0
                bars_in_position = 0

        # Entry: price drops to grid buy level (one spacing below center)
        if position_qty == 0:
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            is_ranging = abs(rsi_val - 50) < 25
            buy_level = grid_center - grid_spacing

            if is_ranging and price <= buy_level and grid_spacing > 0:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)

                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee
                    total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({
                        "entry_time": idx.isoformat(),
                        "exit_time": "",
                        "side": "BUY",
                        "quantity": qty,
                        "entry_price": entry_price,
                        "exit_price": 0,
                        "pnl": 0,
                        "pnl_pct": 0,
                        "fee": round(fee, 2),
                        "reason": "grid_buy_level",
                        "bars_held": 0,
                    })

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({
            "entry_time": entry_time.isoformat() if entry_time else "",
            "exit_time": df.index[-1].isoformat(),
            "side": "SELL",
            "quantity": position_qty,
            "entry_price": entry_price,
            "exit_price": sell_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2),
            "reason": "backtest_end",
            "bars_held": bars_in_position,
        })

    buy_hold_pct = _calculate_buy_hold(df, initial_cash)
    return _calculate_metrics(
        symbol=symbol, strategy="grid", interval=interval,
        initial_cash=initial_cash, equity_curve=equity_curve, trades=trades,
        total_fees=total_fees, total_slippage=total_slippage, buy_hold_return_pct=buy_hold_pct,
    )


# ─── Parameter Optimization (Grid Search) ─────────────────────────────────────


@dataclass
class OptimizationResult:
    """Result of a parameter optimization run."""
    symbol: str
    strategy: str
    interval: str
    total_combinations: int
    best_params: dict
    best_sharpe: float
    best_return_pct: float
    best_win_rate: float
    best_max_drawdown: float
    best_alpha: float
    all_results: list[dict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "interval": self.interval,
            "total_combinations": self.total_combinations,
            "best_params": self.best_params,
            "best_sharpe": round(self.best_sharpe, 2),
            "best_return_pct": round(self.best_return_pct, 2),
            "best_win_rate": round(self.best_win_rate * 100, 1),
            "best_max_drawdown": round(self.best_max_drawdown, 2),
            "best_alpha": round(self.best_alpha, 2),
            "all_results": self.all_results,
        }


def _run_trend_momentum_custom(
    df: pd.DataFrame,
    initial_cash: float,
    fast_ema: int,
    slow_ema: int,
    rsi_upper: float,
    vol_threshold: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
) -> tuple[list[dict], list[dict]]:
    """Run TrendMomentum with custom params on pre-fetched data. Returns (equity_curve, trades)."""
    close = df["close"]
    ema_fast = ind.ema(close, fast_ema)
    ema_slow = ind.ema(close, slow_ema)
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = max(slow_ema, 21) + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            trailing_stop = highest_since_entry * 0.98
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            if price <= effective_stop or price >= take_profit:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": "exit"})
                position_qty = 0.0
                entry_price = 0.0
                highest_since_entry = 0.0
                bars_in_position = 0

        if position_qty == 0:
            ema_f = float(ema_fast.iloc[i])
            ema_s = float(ema_slow.iloc[i])
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            vr = float(vol_rel.iloc[i]) if not vol_rel.isna().iloc[i] else 1.0

            if ema_f > ema_s and rsi_val < rsi_upper and vr > vol_threshold:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)

                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": "end"})

    return equity_curve, trades


def _run_mean_reversion_custom(
    df: pd.DataFrame,
    initial_cash: float,
    rsi_oversold: float,
    rsi_overbought: float,
    bb_std: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
) -> tuple[list[dict], list[dict]]:
    """Run MeanReversion with custom params on pre-fetched data. Returns (equity_curve, trades)."""
    close = df["close"]
    bb = ind.bollinger_bands(close, 20, bb_std)
    bb_upper = bb["upper"]
    bb_middle = bb["middle"]
    bb_lower = bb["lower"]
    bb_width = (bb["upper"] - bb["lower"]) / bb["middle"].replace(0, np.nan)
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0
    max_hold = 24
    trailing_pct = 0.015

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = 21

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            bb_mid = float(bb_middle.iloc[i]) if not bb_middle.isna().iloc[i] else price

            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            if price <= effective_stop:
                exit_reason = "stop_loss"
            elif price >= take_profit:
                exit_reason = "take_profit"
            elif rsi_val > rsi_overbought:
                exit_reason = "rsi_overbought"
            elif price >= bb_mid:
                exit_reason = "reverted_to_mean"
            elif bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": exit_reason})
                position_qty = 0.0
                entry_price = 0.0
                highest_since_entry = 0.0
                bars_in_position = 0

        if position_qty == 0:
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            bb_low = float(bb_lower.iloc[i]) if not bb_lower.isna().iloc[i] else price
            bw = float(bb_width.iloc[i]) if not bb_width.isna().iloc[i] else 0
            vr = float(vol_rel.iloc[i]) if not vol_rel.isna().iloc[i] else 1.0

            if rsi_val < rsi_oversold and price <= bb_low and vr > 1.0 and bw > 0.02:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)

                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": "end"})

    return equity_curve, trades


# ─── MACD Momentum Backtest ───────────────────────────────────────────────────


def _run_macd_momentum(
    symbol: str,
    interval: str,
    limit: int,
    initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.07,
    trailing_pct: float = 0.025,
    max_hold: int = 48,
) -> BacktestResult:
    """Backtest for MACD Momentum strategy."""
    df = _fetch_klines_df(symbol, interval, limit)
    close = df["close"]
    macd_df = ind.macd(close, fast_period, slow_period, signal_period)
    macd_line = macd_df["macd"]
    signal_line = macd_df["signal"]
    histogram = macd_df["histogram"]
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0
    total_fees = 0.0
    total_slippage = 0.0

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = slow_period + signal_period + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            # MACD bearish crossover
            if i > 0 and not macd_line.isna().iloc[i - 1] and not signal_line.isna().iloc[i - 1]:
                if macd_line.iloc[i - 1] >= signal_line.iloc[i - 1] and macd_line.iloc[i] < signal_line.iloc[i]:
                    exit_reason = "macd_bearish_cross"
            if not exit_reason and price <= effective_stop:
                exit_reason = "stop_loss" if price <= hard_stop else "trailing_stop"
            elif not exit_reason and price >= take_profit:
                exit_reason = "take_profit"
            elif not exit_reason and bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(), "side": "SELL",
                    "quantity": position_qty, "entry_price": entry_price, "exit_price": sell_price,
                    "pnl": round(pnl, 2), "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2), "reason": exit_reason, "bars_held": bars_in_position,
                })
                position_qty = 0.0; entry_price = 0.0; highest_since_entry = 0.0; bars_in_position = 0

        if position_qty == 0:
            m_val = float(macd_line.iloc[i]) if not macd_line.isna().iloc[i] else 0
            s_val = float(signal_line.iloc[i]) if not signal_line.isna().iloc[i] else 0
            prev_m = float(macd_line.iloc[i - 1]) if i > 0 and not macd_line.isna().iloc[i - 1] else 0
            prev_s = float(signal_line.iloc[i - 1]) if i > 0 and not signal_line.isna().iloc[i - 1] else 0
            hist = float(histogram.iloc[i]) if not histogram.isna().iloc[i] else 0
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50

            crossover_up = prev_m <= prev_s and m_val > s_val
            if crossover_up and hist > 0 and rsi_val > 45:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)
                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price; position_qty = qty
                    highest_since_entry = price; entry_time = idx; bars_in_position = 0
                    cash -= trade_value + fee; total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({"entry_time": idx.isoformat(), "exit_time": "", "side": "BUY",
                        "quantity": qty, "entry_price": entry_price, "exit_price": 0,
                        "pnl": 0, "pnl_pct": 0, "fee": round(fee, 2), "reason": "macd_bullish_cross", "bars_held": 0})

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee; total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({"entry_time": entry_time.isoformat() if entry_time else "", "exit_time": df.index[-1].isoformat(),
            "side": "SELL", "quantity": position_qty, "entry_price": entry_price, "exit_price": sell_price,
            "pnl": round(pnl, 2), "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2), "reason": "backtest_end", "bars_held": bars_in_position})

    buy_hold_pct = _calculate_buy_hold(df, initial_cash)
    return _calculate_metrics(symbol=symbol, strategy="macd_momentum", interval=interval,
        initial_cash=initial_cash, equity_curve=equity_curve, trades=trades,
        total_fees=total_fees, total_slippage=total_slippage, buy_hold_return_pct=buy_hold_pct)


# ─── Bollinger Squeeze Backtest ───────────────────────────────────────────────


def _run_bollinger_squeeze(
    symbol: str, interval: str, limit: int, initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT, slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    bb_period: int = 20, bb_std: float = 2.0, squeeze_threshold: float = 20.0,
    stop_loss_pct: float = 0.03, take_profit_pct: float = 0.10,
    trailing_pct: float = 0.03, max_hold: int = 60,
) -> BacktestResult:
    """Backtest for Bollinger Squeeze strategy."""
    df = _fetch_klines_df(symbol, interval, limit)
    close = df["close"]
    bb = ind.bollinger_bands(close, bb_period, bb_std)
    bb_upper = bb["upper"]; bb_middle = bb["middle"]; bb_lower = bb["lower"]
    bb_width = (bb["upper"] - bb["lower"]) / bb["middle"].replace(0, np.nan)
    atr_pct = ind.atr_percentile(df, 14, 50)
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)

    cash = initial_cash; position_qty = 0.0; entry_price = 0.0
    highest_since_entry = 0.0; entry_time = None; bars_in_position = 0
    total_fees = 0.0; total_slippage = 0.0
    equity_curve: list[dict] = []; trades: list[dict] = []
    min_bars = 51

    for i in range(min_bars, len(df)):
        idx = df.index[i]; price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            bb_mid = float(bb_middle.iloc[i]) if not bb_middle.isna().iloc[i] else price
            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            if price < bb_mid: exit_reason = "below_bb_mid"
            elif price <= effective_stop: exit_reason = "stop_loss"
            elif price >= take_profit: exit_reason = "take_profit"
            elif bars_in_position >= max_hold: exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee; total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({"entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(), "side": "SELL", "quantity": position_qty,
                    "entry_price": entry_price, "exit_price": sell_price, "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2), "reason": exit_reason, "bars_held": bars_in_position})
                position_qty = 0.0; entry_price = 0.0; highest_since_entry = 0.0; bars_in_position = 0

        if position_qty == 0:
            ap = float(atr_pct.iloc[i]) if not atr_pct.isna().iloc[i] else 50
            prev_upper = float(bb_upper.iloc[i - 1]) if i > 0 and not bb_upper.isna().iloc[i - 1] else 0
            bw = float(bb_width.iloc[i]) if not bb_width.isna().iloc[i] else 0
            prev_bw = float(bb_width.iloc[i - 1]) if i > 0 and not bb_width.isna().iloc[i - 1] else 0
            in_squeeze = ap < squeeze_threshold
            price_breakout = price > prev_upper
            width_expanding = bw > prev_bw

            if in_squeeze and price_breakout and width_expanding:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)
                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price; position_qty = qty
                    highest_since_entry = price; entry_time = idx; bars_in_position = 0
                    cash -= trade_value + fee; total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({"entry_time": idx.isoformat(), "exit_time": "", "side": "BUY",
                        "quantity": qty, "entry_price": entry_price, "exit_price": 0,
                        "pnl": 0, "pnl_pct": 0, "fee": round(fee, 2), "reason": "squeeze_breakout", "bars_held": 0})

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee; total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({"entry_time": entry_time.isoformat() if entry_time else "", "exit_time": df.index[-1].isoformat(),
            "side": "SELL", "quantity": position_qty, "entry_price": entry_price, "exit_price": sell_price,
            "pnl": round(pnl, 2), "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2), "reason": "backtest_end", "bars_held": bars_in_position})

    buy_hold_pct = _calculate_buy_hold(df, initial_cash)
    return _calculate_metrics(symbol=symbol, strategy="bollinger_squeeze", interval=interval,
        initial_cash=initial_cash, equity_curve=equity_curve, trades=trades,
        total_fees=total_fees, total_slippage=total_slippage, buy_hold_return_pct=buy_hold_pct)


# ─── Supertrend Backtest ──────────────────────────────────────────────────────


def _run_supertrend(
    symbol: str, interval: str, limit: int, initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT, slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    atr_period: int = 10, multiplier: float = 3.0,
    stop_loss_pct: float = 0.04, take_profit_pct: float = 0.12,
    trailing_pct: float = 0.035, max_hold: int = 72,
) -> BacktestResult:
    """Backtest for Supertrend strategy."""
    df = _fetch_klines_df(symbol, interval, limit)
    close = df["close"]
    st = ind.supertrend(df, atr_period, multiplier)
    st_line = st["supertrend"]; st_dir = st["direction"]
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)

    cash = initial_cash; position_qty = 0.0; entry_price = 0.0
    highest_since_entry = 0.0; entry_time = None; bars_in_position = 0
    total_fees = 0.0; total_slippage = 0.0
    equity_curve: list[dict] = []; trades: list[dict] = []
    min_bars = atr_period * 2 + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]; price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            cur_dir = float(st_dir.iloc[i]) if not st_dir.isna().iloc[i] else 1
            prev_dir = float(st_dir.iloc[i - 1]) if i > 0 and not st_dir.isna().iloc[i - 1] else 1
            if prev_dir == 1 and cur_dir == -1: exit_reason = "supertrend_bearish"
            elif price <= effective_stop: exit_reason = "stop_loss"
            elif price >= take_profit: exit_reason = "take_profit"
            elif bars_in_position >= max_hold: exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee; total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({"entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(), "side": "SELL", "quantity": position_qty,
                    "entry_price": entry_price, "exit_price": sell_price, "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2), "reason": exit_reason, "bars_held": bars_in_position})
                position_qty = 0.0; entry_price = 0.0; highest_since_entry = 0.0; bars_in_position = 0

        if position_qty == 0:
            cur_dir = float(st_dir.iloc[i]) if not st_dir.isna().iloc[i] else 0
            prev_dir = float(st_dir.iloc[i - 1]) if i > 0 and not st_dir.isna().iloc[i - 1] else 0
            st_val = float(st_line.iloc[i]) if not st_line.isna().iloc[i] else 0
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50

            trend_up = prev_dir == -1 and cur_dir == 1
            if trend_up and price > st_val and rsi_val > 45:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)
                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price; position_qty = qty
                    highest_since_entry = price; entry_time = idx; bars_in_position = 0
                    cash -= trade_value + fee; total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({"entry_time": idx.isoformat(), "exit_time": "", "side": "BUY",
                        "quantity": qty, "entry_price": entry_price, "exit_price": 0,
                        "pnl": 0, "pnl_pct": 0, "fee": round(fee, 2), "reason": "supertrend_bullish", "bars_held": 0})

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee; total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({"entry_time": entry_time.isoformat() if entry_time else "", "exit_time": df.index[-1].isoformat(),
            "side": "SELL", "quantity": position_qty, "entry_price": entry_price, "exit_price": sell_price,
            "pnl": round(pnl, 2), "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2), "reason": "backtest_end", "bars_held": bars_in_position})

    buy_hold_pct = _calculate_buy_hold(df, initial_cash)
    return _calculate_metrics(symbol=symbol, strategy="supertrend", interval=interval,
        initial_cash=initial_cash, equity_curve=equity_curve, trades=trades,
        total_fees=total_fees, total_slippage=total_slippage, buy_hold_return_pct=buy_hold_pct)


# ─── RSI Divergence Backtest ──────────────────────────────────────────────────


def _run_rsi_divergence(
    symbol: str, interval: str, limit: int, initial_cash: float,
    fee_pct: float = DEFAULT_FEE_PCT, slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    rsi_period: int = 14, divergence_lookback: int = 20,
    rsi_oversold: float = 35.0, rsi_overbought: float = 65.0,
    stop_loss_pct: float = 0.03, take_profit_pct: float = 0.06,
    trailing_pct: float = 0.02, max_hold: int = 36,
) -> BacktestResult:
    """Backtest for RSI Divergence strategy."""
    df = _fetch_klines_df(symbol, interval, limit)
    close = df["close"]
    rsi_series = ind.rsi(close, rsi_period)
    atr_series = ind.atr(df, 14)

    cash = initial_cash; position_qty = 0.0; entry_price = 0.0
    highest_since_entry = 0.0; entry_time = None; bars_in_position = 0
    total_fees = 0.0; total_slippage = 0.0
    equity_curve: list[dict] = []; trades: list[dict] = []
    min_bars = max(divergence_lookback + 10, rsi_period + 10, 30)

    def find_pivot_lows(series, lookback):
        pivots = []
        vals = series.values
        for j in range(2, len(vals) - 2):
            if j < len(vals) - lookback: continue
            if np.isnan(vals[j]): continue
            if vals[j] < vals[j-1] and vals[j] < vals[j+1] and vals[j] < vals[j-2] and vals[j] < vals[j+2]:
                pivots.append((j, float(vals[j])))
        return pivots

    for i in range(min_bars, len(df)):
        idx = df.index[i]; price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50
            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            if rsi_val > rsi_overbought: exit_reason = "rsi_overbought"
            elif price <= effective_stop: exit_reason = "stop_loss"
            elif price >= take_profit: exit_reason = "take_profit"
            elif bars_in_position >= max_hold: exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee; total_fees += fee
                total_slippage += (price - sell_price) * position_qty
                trades.append({"entry_time": entry_time.isoformat() if entry_time else "",
                    "exit_time": idx.isoformat(), "side": "SELL", "quantity": position_qty,
                    "entry_price": entry_price, "exit_price": sell_price, "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
                    "fee": round(fee, 2), "reason": exit_reason, "bars_held": bars_in_position})
                position_qty = 0.0; entry_price = 0.0; highest_since_entry = 0.0; bars_in_position = 0

        if position_qty == 0:
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50
            # Detect bullish divergence
            price_lows = find_pivot_lows(df["close"].iloc[:i+1], divergence_lookback)
            rsi_lows = find_pivot_lows(rsi_series.iloc[:i+1], divergence_lookback)
            bullish_div = False
            if len(price_lows) >= 2 and len(rsi_lows) >= 2:
                p1_idx, p1_val = price_lows[-2]; p2_idx, p2_val = price_lows[-1]
                r1_idx, r1_val = rsi_lows[-2]; r2_idx, r2_val = rsi_lows[-1]
                if p2_val < p1_val and r2_val > r1_val and rsi_val < rsi_oversold:
                    bullish_div = True

            if bullish_div:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)
                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price; position_qty = qty
                    highest_since_entry = price; entry_time = idx; bars_in_position = 0
                    cash -= trade_value + fee; total_fees += fee
                    total_slippage += (fill_price - price) * qty
                    trades.append({"entry_time": idx.isoformat(), "exit_time": "", "side": "BUY",
                        "quantity": qty, "entry_price": entry_price, "exit_price": 0,
                        "pnl": 0, "pnl_pct": 0, "fee": round(fee, 2), "reason": "rsi_bullish_divergence", "bars_held": 0})

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee; total_fees += fee
        total_slippage += (final_price - sell_price) * position_qty
        trades.append({"entry_time": entry_time.isoformat() if entry_time else "", "exit_time": df.index[-1].isoformat(),
            "side": "SELL", "quantity": position_qty, "entry_price": entry_price, "exit_price": sell_price,
            "pnl": round(pnl, 2), "pnl_pct": round((pnl / (entry_price * position_qty)) * 100, 2) if entry_price > 0 else 0,
            "fee": round(fee, 2), "reason": "backtest_end", "bars_held": bars_in_position})

    buy_hold_pct = _calculate_buy_hold(df, initial_cash)
    return _calculate_metrics(symbol=symbol, strategy="rsi_divergence", interval=interval,
        initial_cash=initial_cash, equity_curve=equity_curve, trades=trades,
        total_fees=total_fees, total_slippage=total_slippage, buy_hold_return_pct=buy_hold_pct)


def _run_breakout_custom(
    df: pd.DataFrame,
    initial_cash: float,
    donchian_period: int = 20,
    volume_threshold: float = 1.5,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.08,
    trailing_pct: float = 0.025,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
) -> tuple[list[dict], list[dict]]:
    """Run Breakout with custom params on pre-fetched data. Returns (equity_curve, trades)."""
    close = df["close"]
    dc = ind.donchian_channels(df, donchian_period)
    dc_upper = dc["upper"]
    dc_middle = dc["middle"]
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)
    vol_rel = ind.relative_volume(df["volume"], 20)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    entry_time = None
    bars_in_position = 0
    max_hold = 48

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = donchian_period + 1

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        if position_qty > 0:
            bars_in_position += 1
            highest_since_entry = max(highest_since_entry, price)
            dc_mid = float(dc_middle.iloc[i]) if not dc_middle.isna().iloc[i] else price
            trailing_stop = highest_since_entry * (1 - trailing_pct)
            hard_stop = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
            effective_stop = max(trailing_stop, hard_stop)

            exit_reason = None
            if price <= effective_stop:
                exit_reason = "stop_loss"
            elif price >= take_profit:
                exit_reason = "take_profit"
            elif price < dc_mid:
                exit_reason = "below_mid"
            elif bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": exit_reason})
                position_qty = 0.0
                entry_price = 0.0
                highest_since_entry = 0.0
                bars_in_position = 0

        if position_qty == 0:
            prev_upper = float(dc_upper.iloc[i - 1]) if i > 0 and not dc_upper.isna().iloc[i - 1] else 0
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            vr = float(vol_rel.iloc[i]) if not vol_rel.isna().iloc[i] else 1.0

            if price > prev_upper and vr > volume_threshold and rsi_val > 40:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)
                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    highest_since_entry = price
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": "end"})

    return equity_curve, trades


def _run_grid_custom(
    df: pd.DataFrame,
    initial_cash: float,
    atr_multiplier: float = 2.0,
    grid_levels: int = 5,
    stop_loss_pct: float = 0.04,
    fee_pct: float = DEFAULT_FEE_PCT,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
) -> tuple[list[dict], list[dict]]:
    """Run Grid with custom params on pre-fetched data. Returns (equity_curve, trades)."""
    close = df["close"]
    rsi_series = ind.rsi(close, 14)
    atr_series = ind.atr(df, 14)

    cash = initial_cash
    position_qty = 0.0
    entry_price = 0.0
    entry_time = None
    bars_in_position = 0
    max_hold = 72
    grid_center = 0.0
    grid_spacing = 0.0

    equity_curve: list[dict] = []
    trades: list[dict] = []
    min_bars = 15

    for i in range(min_bars, len(df)):
        idx = df.index[i]
        price = float(df.iloc[i]["close"])

        if position_qty == 0 and i > 0:
            atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
            grid_center = float(df.iloc[i - 1]["close"])
            grid_spacing = (atr_val * atr_multiplier) / grid_levels

        if position_qty > 0:
            bars_in_position += 1
            sell_level = entry_price + grid_spacing
            hard_stop = entry_price * (1 - stop_loss_pct)

            exit_reason = None
            if price >= sell_level:
                exit_reason = "grid_sell"
            elif price <= hard_stop:
                exit_reason = "stop_loss"
            elif bars_in_position >= max_hold:
                exit_reason = "max_hold"

            if exit_reason:
                sell_price = _apply_slippage_sell(price, slippage_pct)
                trade_value = position_qty * sell_price
                fee = _calculate_fee(trade_value, fee_pct)
                pnl = (sell_price - entry_price) * position_qty - fee
                cash += trade_value - fee
                trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": exit_reason})
                position_qty = 0.0
                entry_price = 0.0
                bars_in_position = 0

        if position_qty == 0:
            rsi_val = float(rsi_series.iloc[i]) if not rsi_series.isna().iloc[i] else 50.0
            is_ranging = abs(rsi_val - 50) < 25
            buy_level = grid_center - grid_spacing

            if is_ranging and price <= buy_level and grid_spacing > 0:
                atr_val = float(atr_series.iloc[i]) if not atr_series.isna().iloc[i] else price * 0.02
                risk_amount = cash * 0.02
                stop_distance = max(atr_val * 1.5, price * stop_loss_pct)
                qty = risk_amount / stop_distance
                fill_price = _apply_slippage_buy(price, slippage_pct)
                trade_value = qty * fill_price
                fee = _calculate_fee(trade_value, fee_pct)
                if qty > 0 and cash > trade_value + fee:
                    entry_price = fill_price
                    position_qty = qty
                    entry_time = idx
                    bars_in_position = 0
                    cash -= trade_value + fee

        equity = cash + (position_qty * price if position_qty > 0 else 0)
        equity_curve.append({"time": idx.isoformat(), "equity": round(equity, 2), "price": round(price, 6)})

    if position_qty > 0:
        final_price = float(df.iloc[-1]["close"])
        sell_price = _apply_slippage_sell(final_price, slippage_pct)
        trade_value = position_qty * sell_price
        fee = _calculate_fee(trade_value, fee_pct)
        pnl = (sell_price - entry_price) * position_qty - fee
        cash += trade_value - fee
        trades.append({"side": "SELL", "pnl": pnl, "entry_price": entry_price, "exit_price": sell_price, "reason": "end"})

    return equity_curve, trades


# Parameter grids for optimization
_TREND_PARAMS = {
    "fast_ema": [5, 9, 12],
    "slow_ema": [21, 26, 50],
    "rsi_upper": [55, 60, 65],
    "vol_threshold": [0.8, 1.0, 1.5],
    "stop_loss_pct": [0.02, 0.03, 0.04],
    "take_profit_pct": [0.04, 0.06, 0.08],
}

_MEANREV_PARAMS = {
    "rsi_oversold": [25, 30, 35],
    "rsi_overbought": [65, 70, 75],
    "bb_std": [1.5, 2.0, 2.5],
    "stop_loss_pct": [0.02, 0.025, 0.03],
    "take_profit_pct": [0.03, 0.04, 0.05],
}

_BREAKOUT_PARAMS = {
    "donchian_period": [10, 20, 30],
    "volume_threshold": [1.0, 1.5, 2.0],
    "stop_loss_pct": [0.02, 0.03, 0.04],
    "take_profit_pct": [0.05, 0.08, 0.12],
    "trailing_pct": [0.02, 0.025, 0.03],
}

_GRID_PARAMS = {
    "atr_multiplier": [1.5, 2.0, 3.0],
    "grid_levels": [3, 5, 8],
    "stop_loss_pct": [0.03, 0.04, 0.05],
}


def run_optimization(
    symbol: str,
    strategy: str = "trend_momentum",
    interval: str = "1h",
    limit: int = 500,
    initial_cash: float = 10000.0,
    max_combinations: int = 50,
) -> OptimizationResult:
    """Run grid search optimization for a strategy.

    Tries multiple parameter combinations and returns the best one by Sharpe ratio.
    Limits to max_combinations to avoid excessive runtime.
    """
    import itertools

    df = _fetch_klines_df(symbol, interval, limit)
    buy_hold_pct = _calculate_buy_hold(df, initial_cash)

    if strategy == "mean_reversion":
        param_grid = _MEANREV_PARAMS
    elif strategy == "breakout":
        param_grid = _BREAKOUT_PARAMS
    elif strategy == "grid":
        param_grid = _GRID_PARAMS
    else:
        param_grid = _TREND_PARAMS
    keys = list(param_grid.keys())
    all_combos = list(itertools.product(*[param_grid[k] for k in keys]))

    # Limit combinations — pick evenly spaced subset if too many
    if len(all_combos) > max_combinations:
        step = len(all_combos) / max_combinations
        all_combos = [all_combos[int(i * step)] for i in range(max_combinations)]

    all_results: list[dict] = []
    best_sharpe = -999.0
    best_result = None

    for combo in all_combos:
        params = dict(zip(keys, combo))

        if strategy == "mean_reversion":
            eq, tr = _run_mean_reversion_custom(df, initial_cash, **params)
        elif strategy == "breakout":
            eq, tr = _run_breakout_custom(df, initial_cash, **params)
        elif strategy == "grid":
            eq, tr = _run_grid_custom(df, initial_cash, **params)
        else:
            eq, tr = _run_trend_momentum_custom(df, initial_cash, **params)

        # Calculate metrics
        if not eq:
            continue
        equity_series = pd.Series([e["equity"] for e in eq])
        final_equity = float(equity_series.iloc[-1])
        total_return = (final_equity - initial_cash) / initial_cash * 100

        bars_per_year = {"1m": 525600, "5m": 105120, "15m": 35040, "1h": 8760, "4h": 2190, "1d": 365}
        bpy = bars_per_year.get(interval, 8760)
        returns = equity_series.pct_change().dropna()
        sharpe = float(returns.mean() / returns.std() * np.sqrt(bpy)) if len(returns) > 1 and returns.std() != 0 else 0.0

        rolling_max = equity_series.cummax()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_dd = float(drawdown.min()) * 100 if len(drawdown) > 0 else 0.0

        sell_trades = [t for t in tr if t["side"] == "SELL" and t["pnl"] != 0]
        total_closed = len(sell_trades)
        wins = sum(1 for t in sell_trades if t["pnl"] > 0)
        win_rate = wins / total_closed if total_closed else 0.0

        alpha = total_return - buy_hold_pct

        result_entry = {
            "params": params,
            "total_return_pct": round(total_return, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "win_rate": round(win_rate * 100, 1),
            "total_trades": total_closed,
            "alpha": round(alpha, 2),
        }
        all_results.append(result_entry)

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_result = result_entry

    # Sort all results by Sharpe descending
    all_results.sort(key=lambda x: x["sharpe"], reverse=True)

    if best_result is None:
        best_result = {"params": {}, "total_return_pct": 0, "sharpe": 0, "max_drawdown_pct": 0, "win_rate": 0, "total_trades": 0, "alpha": 0}

    return OptimizationResult(
        symbol=symbol.upper(),
        strategy=strategy,
        interval=interval,
        total_combinations=len(all_combos),
        best_params=best_result["params"],
        best_sharpe=best_result["sharpe"],
        best_return_pct=best_result["total_return_pct"],
        best_win_rate=best_result["win_rate"] / 100,
        best_max_drawdown=best_result["max_drawdown_pct"],
        best_alpha=best_result["alpha"],
        all_results=all_results[:20],  # Top 20
    )
