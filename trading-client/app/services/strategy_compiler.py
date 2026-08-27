"""Strategy compiler — compiles visual strategy builder configs to executable functions.

Takes a JSON config from the Visual Strategy Builder (F4.1) and:
  1. Validates the config makes sense (validate_strategy)
  2. Compiles it to an executable function (compile_strategy)
  3. Runs a backtest with the compiled strategy (backtest_custom_strategy)

The visual config consists of blocks:
  - Entry: price_above, price_below, rsi_level, ma_cross, volume_spike, ai_signal
  - Exit: take_profit, stop_loss, trailing_stop, time_exit
  - Sizing: fixed_usd, pct_portfolio, kelly
  - Risk: max_positions, max_drawdown, regime_filter
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.indicators import indicators as ind

logger = logging.getLogger(__name__)


# ─── Validation ───────────────────────────────────────────────────────────────


def validate_strategy(json_config: dict) -> dict[str, Any]:
    """Validate a visual strategy config.

    Returns:
        {"valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    blocks = json_config.get("blocks", [])
    if not blocks:
        errors.append("Strategy has no blocks")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Check required categories
    categories = {b.get("category") for b in blocks}
    if "entry" not in categories:
        errors.append("At least one Entry block is required")
    if "exit" not in categories:
        errors.append("At least one Exit block is required")
    if "sizing" not in categories:
        errors.append("A Position Sizing block is required")

    # Check for too many entry blocks
    entry_count = sum(1 for b in blocks if b.get("category") == "entry")
    if entry_count > 3:
        warnings.append("More than 3 entry blocks — strategy may be over-fitted")

    # Validate individual block params
    for i, block in enumerate(blocks):
        btype = block.get("type", "")
        params = block.get("params", {})
        if not btype:
            errors.append(f"Block {i} has no type")
            continue

        # Type-specific validation
        if btype == "exit_take_profit":
            tp = params.get("tp_pct", 0)
            if tp <= 0 or tp > 100:
                errors.append(f"Block {i} ({btype}): tp_pct must be between 0 and 100")
        elif btype == "exit_stop_loss":
            sl = params.get("sl_pct", 0)
            if sl <= 0 or sl > 100:
                errors.append(f"Block {i} ({btype}): sl_pct must be between 0 and 100")
        elif btype == "entry_rsi_level":
            rsi_level = params.get("rsi_level", 30)
            if rsi_level < 1 or rsi_level > 99:
                errors.append(f"Block {i} ({btype}): rsi_level must be between 1 and 99")
        elif btype == "entry_ma_cross":
            fast = params.get("fast_period", 9)
            slow = params.get("slow_period", 21)
            if fast >= slow:
                warnings.append(f"Block {i} ({btype}): fast_period should be less than slow_period")
        elif btype == "sizing_kelly":
            kelly_frac = params.get("kelly_fraction", 0.5)
            if kelly_frac > 1:
                errors.append(f"Block {i} ({btype}): kelly_fraction should not exceed 1.0")
        elif btype == "risk_max_drawdown":
            max_dd = params.get("max_dd_pct", 15)
            if max_dd <= 0 or max_dd > 50:
                warnings.append(f"Block {i} ({btype}): max_dd_pct of {max_dd}% is aggressive")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# ─── Compilation ──────────────────────────────────────────────────────────────


@dataclass
class CompiledStrategy:
    """A compiled strategy ready for backtesting."""

    name: str
    entry_blocks: list[dict] = field(default_factory=list)
    exit_blocks: list[dict] = field(default_factory=list)
    sizing_block: dict | None = None
    risk_blocks: list[dict] = field(default_factory=list)

    def check_entry(self, df: pd.DataFrame, i: int, position: dict | None) -> bool:
        """Check if any entry condition is met at bar i."""
        for block in self.entry_blocks:
            if _check_entry_block(block, df, i):
                return True
        return False

    def check_exit(self, df: pd.DataFrame, i: int, position: dict) -> bool:
        """Check if any exit condition is met at bar i."""
        for block in self.exit_blocks:
            if _check_exit_block(block, df, i, position):
                return True
        return False

    def calculate_size(self, cash: float, equity: float, df: pd.DataFrame, i: int) -> float:
        """Calculate position size in USD."""
        if not self.sizing_block:
            return min(cash, 100)  # default $100

        block = self.sizing_block
        stype = block["type"]
        params = block.get("params", {})

        if stype == "sizing_fixed_usd":
            return min(params.get("amount", 100), cash)
        elif stype == "sizing_pct_portfolio":
            pct = params.get("pct", 5) / 100
            return min(equity * pct, cash)
        elif stype == "sizing_kelly":
            kelly_frac = params.get("kelly_fraction", 0.5)
            win_rate = params.get("win_rate", 55) / 100
            win_loss = params.get("win_loss_ratio", 1.5)
            # Kelly formula: f = (p*b - q) / b
            b = win_loss
            p = win_rate
            q = 1 - p
            kelly = (p * b - q) / b if b > 0 else 0
            kelly = max(0, kelly * kelly_frac)
            return min(equity * kelly, cash)
        return min(cash, 100)

    def check_risk(self, equity: float, initial_cash: float, open_positions: int) -> tuple[bool, str]:
        """Check risk filters. Returns (allowed, reason)."""
        for block in self.risk_blocks:
            rtype = block["type"]
            params = block.get("params", {})
            if rtype == "risk_max_positions":
                max_pos = params.get("max_positions", 5)
                if open_positions >= max_pos:
                    return False, f"Max positions ({max_pos}) reached"
            elif rtype == "risk_max_drawdown":
                max_dd = params.get("max_dd_pct", 15)
                dd_pct = (initial_cash - equity) / initial_cash * 100 if initial_cash > 0 else 0
                if dd_pct >= max_dd:
                    return False, f"Max drawdown ({max_dd}%) reached"
        return True, ""


def compile_strategy(json_config: dict) -> CompiledStrategy:
    """Compile a visual strategy config into a CompiledStrategy object.

    Args:
        json_config: Strategy config from the Visual Strategy Builder.
            Expected format: {"name": str, "blocks": [{"type": str, "category": str, "params": dict}]}

    Returns:
        CompiledStrategy ready for backtesting.

    Raises:
        ValueError: If the config is invalid.
    """
    validation = validate_strategy(json_config)
    if not validation["valid"]:
        raise ValueError(f"Invalid strategy config: {'; '.join(validation['errors'])}")

    blocks = json_config.get("blocks", [])
    compiled = CompiledStrategy(name=json_config.get("name", "Custom Strategy"))

    for block in blocks:
        cat = block.get("category")
        if cat == "entry":
            compiled.entry_blocks.append(block)
        elif cat == "exit":
            compiled.exit_blocks.append(block)
        elif cat == "sizing":
            compiled.sizing_block = block
        elif cat == "risk":
            compiled.risk_blocks.append(block)

    return compiled


# ─── Entry block checkers ─────────────────────────────────────────────────────


def _check_entry_block(block: dict, df: pd.DataFrame, i: int) -> bool:
    """Check if an entry condition is met at bar i."""
    btype = block["type"]
    params = block.get("params", {})

    if i < 2:
        return False

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    if btype == "entry_price_above":
        lookback = int(params.get("lookback", 20))
        threshold_pct = params.get("threshold_pct", 2) / 100
        if i < lookback:
            return False
        ref_price = close.iloc[i - lookback]
        current = close.iloc[i]
        return current > ref_price * (1 + threshold_pct)

    elif btype == "entry_price_below":
        lookback = int(params.get("lookback", 20))
        threshold_pct = params.get("threshold_pct", 2) / 100
        if i < lookback:
            return False
        ref_price = close.iloc[i - lookback]
        current = close.iloc[i]
        return current < ref_price * (1 - threshold_pct)

    elif btype == "entry_rsi_level":
        period = int(params.get("rsi_period", 14))
        level = params.get("rsi_level", 30)
        direction = params.get("direction", "oversold")
        if i < period + 1:
            return False
        rsi_series = ind.rsi(close, period)
        rsi_val = rsi_series.iloc[i]
        rsi_prev = rsi_series.iloc[i - 1]
        if pd.isna(rsi_val) or pd.isna(rsi_prev):
            return False
        if direction == "oversold":
            return rsi_prev < level and rsi_val >= level
        else:
            return rsi_prev > level and rsi_val <= level

    elif btype == "entry_ma_cross":
        fast_period = int(params.get("fast_period", 9))
        slow_period = int(params.get("slow_period", 21))
        ma_type = params.get("ma_type", "ema")
        if i < slow_period + 1:
            return False
        if ma_type == "sma":
            fast = ind.sma(close, fast_period)
            slow = ind.sma(close, slow_period)
        else:
            fast = ind.ema(close, fast_period)
            slow = ind.ema(close, slow_period)
        fast_val = fast.iloc[i]
        slow_val = slow.iloc[i]
        fast_prev = fast.iloc[i - 1]
        slow_prev = slow.iloc[i - 1]
        if pd.isna(fast_val) or pd.isna(slow_val):
            return False
        # Bullish cross: fast crosses above slow
        return fast_prev <= slow_prev and fast_val > slow_val

    elif btype == "entry_volume_spike":
        multiplier = params.get("multiplier", 2)
        lookback = int(params.get("lookback", 20))
        if i < lookback:
            return False
        avg_vol = volume.iloc[i - lookback:i].mean()
        if avg_vol > 0 and volume.iloc[i] > avg_vol * multiplier:
            return True
        return False

    elif btype == "entry_ai_signal":
        # AI signal entry — in backtest we simulate with a momentum proxy
        # (price above EMA50 as a proxy for AI bullish signal)
        period = 50
        if i < period:
            return False
        ema50 = ind.ema(close, period)
        confidence = params.get("confidence", 70) / 100
        signal_type = params.get("signal_type", "buy")
        ema_val = ema50.iloc[i]
        if pd.isna(ema_val):
            return False
        momentum = (close.iloc[i] - ema_val) / ema_val
        if signal_type == "buy":
            return momentum > confidence * 0.02  # scale confidence to momentum threshold
        else:
            return momentum < -confidence * 0.02

    return False


# ─── Exit block checkers ──────────────────────────────────────────────────────


def _check_exit_block(block: dict, df: pd.DataFrame, i: int, position: dict) -> bool:
    """Check if an exit condition is met at bar i."""
    btype = block["type"]
    params = block.get("params", {})
    entry_price = position.get("entry_price", 0)
    entry_bar = position.get("entry_bar", 0)
    highest_since_entry = position.get("highest", entry_price)

    current_price = df["close"].iloc[i]

    if btype == "exit_take_profit":
        tp_pct = params.get("tp_pct", 5) / 100
        return current_price >= entry_price * (1 + tp_pct)

    elif btype == "exit_stop_loss":
        sl_pct = params.get("sl_pct", 3) / 100
        return current_price <= entry_price * (1 - sl_pct)

    elif btype == "exit_trailing_stop":
        trail_pct = params.get("trail_pct", 2) / 100
        activation_pct = params.get("activation_pct", 1) / 100
        # Update highest price since entry
        if current_price > highest_since_entry:
            highest_since_entry = current_price
        # Only activate after price has risen by activation_pct
        if highest_since_entry >= entry_price * (1 + activation_pct):
            return current_price <= highest_since_entry * (1 - trail_pct)
        return False

    elif btype == "exit_time_exit":
        max_bars = int(params.get("max_bars", 48))
        return (i - entry_bar) >= max_bars

    return False


# ─── Backtest ─────────────────────────────────────────────────────────────────


# Fee and slippage constants (same as backtest_service)
DEFAULT_FEE_PCT = 0.001
DEFAULT_SLIPPAGE_PCT = 0.0005


def backtest_custom_strategy(
    user_id: int,
    config: dict,
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
    initial_cash: float = 10000.0,
) -> dict[str, Any]:
    """Run a backtest with a custom compiled strategy.

    Args:
        user_id: User ID (for potential future use with broker credentials).
        config: Visual strategy config from the Strategy Builder.
        symbol: Trading symbol (e.g. "BTCUSDT").
        interval: Kline interval.
        limit: Number of candles to fetch.
        initial_cash: Starting capital.

    Returns:
        Backtest result dict with metrics, equity curve, and trades.
    """
    # Validate first
    validation = validate_strategy(config)
    if not validation["valid"]:
        return {"error": "; ".join(validation["errors"])}

    # Compile strategy
    try:
        strategy = compile_strategy(config)
    except ValueError as e:
        return {"error": str(e)}

    # Fetch klines
    try:
        from app.services.backtest_service import _fetch_klines_df
        df = _fetch_klines_df(symbol, interval, limit)
    except Exception as exc:
        logger.error("Failed to fetch klines for custom backtest: %s", exc)
        return {"error": f"Failed to fetch market data: {exc}"}

    if len(df) < 50:
        return {"error": "Not enough data for backtest (need at least 50 candles)"}

    # Run simulation
    cash = initial_cash
    position: dict | None = None
    equity_curve: list[dict] = []
    trades: list[dict] = []
    peak_equity = initial_cash
    max_drawdown = 0.0

    for i in range(len(df)):
        current_price = float(df["close"].iloc[i])
        timestamp = df.index[i].isoformat() if hasattr(df.index[i], "isoformat") else str(df.index[i])

        # Check exit if in position
        if position:
            # Update highest price for trailing stop
            if current_price > position.get("highest", 0):
                position["highest"] = current_price

            if strategy.check_exit(df, i, position):
                # Close position
                exit_price = current_price * (1 - DEFAULT_SLIPPAGE_PCT)
                trade_value = position["qty"] * exit_price
                fee = trade_value * DEFAULT_FEE_PCT
                cash += trade_value - fee
                pnl = (exit_price - position["entry_price"]) * position["qty"] - fee - position.get("entry_fee", 0)
                trades.append({
                    "entry_bar": position["entry_bar"],
                    "exit_bar": i,
                    "entry_price": round(position["entry_price"], 6),
                    "exit_price": round(exit_price, 6),
                    "qty": round(position["qty"], 6),
                    "pnl": round(pnl, 2),
                    "return_pct": round((exit_price / position["entry_price"] - 1) * 100, 2),
                    "bars_held": i - position["entry_bar"],
                })
                position = None

        # Check entry if not in position
        if not position:
            equity = cash
            # Check risk filters
            allowed, reason = strategy.check_risk(equity, initial_cash, 0)
            if allowed and strategy.check_entry(df, i, None):
                size_usd = strategy.calculate_size(cash, equity, df, i)
                if size_usd > 0 and size_usd <= cash:
                    entry_price = current_price * (1 + DEFAULT_SLIPPAGE_PCT)
                    fee = size_usd * DEFAULT_FEE_PCT
                    qty = (size_usd - fee) / entry_price
                    cash -= size_usd
                    position = {
                        "entry_price": entry_price,
                        "entry_bar": i,
                        "qty": qty,
                        "highest": entry_price,
                        "entry_fee": fee,
                    }

        # Calculate equity
        equity = cash + (position["qty"] * current_price if position else 0)
        equity_curve.append({"time": timestamp, "equity": round(equity, 2)})

        # Track drawdown
        if equity > peak_equity:
            peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

    # Close any remaining position at last price
    if position:
        last_price = float(df["close"].iloc[-1]) * (1 - DEFAULT_SLIPPAGE_PCT)
        trade_value = position["qty"] * last_price
        fee = trade_value * DEFAULT_FEE_PCT
        cash += trade_value - fee
        pnl = (last_price - position["entry_price"]) * position["qty"] - fee - position.get("entry_fee", 0)
        trades.append({
            "entry_bar": position["entry_bar"],
            "exit_bar": len(df) - 1,
            "entry_price": round(position["entry_price"], 6),
            "exit_price": round(last_price, 6),
            "qty": round(position["qty"], 6),
            "pnl": round(pnl, 2),
            "return_pct": round((last_price / position["entry_price"] - 1) * 100, 2),
            "bars_held": len(df) - 1 - position["entry_bar"],
        })

    final_equity = cash

    # Calculate metrics
    total_return_pct = (final_equity - initial_cash) / initial_cash * 100
    total_trades = len(trades)
    winning_trades = [t for t in trades if t["pnl"] > 0]
    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    gross_profit = sum(t["pnl"] for t in winning_trades)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    avg_trade_pnl = sum(t["pnl"] for t in trades) / total_trades if total_trades > 0 else 0

    # Buy and hold
    first_price = float(df["close"].iloc[0])
    last_price = float(df["close"].iloc[-1])
    buy_hold_return = (last_price / first_price - 1) * 100

    # Annualized return (approximate based on interval)
    interval_hours = {"5m": 5 / 60, "15m": 0.25, "1h": 1, "4h": 4, "1d": 24}.get(interval, 1)
    total_hours = len(df) * interval_hours
    years = total_hours / 8760 if total_hours > 0 else 1
    annualized = ((final_equity / initial_cash) ** (1 / years) - 1) * 100 if years > 0 else 0

    return {
        "symbol": symbol,
        "strategy": config.get("name", "Custom Strategy"),
        "interval": interval,
        "initial_cash": initial_cash,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(annualized, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999,
        "total_trades": total_trades,
        "avg_trade_pnl": round(avg_trade_pnl, 2),
        "buy_hold_return_pct": round(buy_hold_return, 2),
        "alpha_pct": round(total_return_pct - buy_hold_return, 2),
        "equity_curve": equity_curve,
        "trades": trades,
        "validation_warnings": validation.get("warnings", []),
    }
