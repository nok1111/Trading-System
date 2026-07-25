"""Cálculo de métricas de rendimiento a partir de equity curve y trades."""

from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


class MetricsCalculator:
    """Calcula métricas clásicas de backtesting."""

    @staticmethod
    def calculate(
        equity_curve: pd.Series,
        trades_df: pd.DataFrame,
        initial_cash: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Devuelve un diccionario con métricas Decimal/float/int."""
        equity = equity_curve.astype(float)
        final_equity = float(equity.iloc[-1])
        total_return_pct = (final_equity - initial_cash) / initial_cash * 100

        n_days = max((end_date - start_date).days, 1)
        annualized = ((final_equity / initial_cash) ** (365.0 / n_days) - 1) * 100

        returns = equity.pct_change().dropna()
        sharpe = 0.0
        if len(returns) > 1 and returns.std() != 0:
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252))

        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        max_dd = float(drawdown.min()) * 100

        closed = (
            trades_df[trades_df["side"] == "SELL"]
            if not trades_df.empty
            else pd.DataFrame(columns=["realized_pnl"])
        )
        total = len(closed)
        wins = int((closed["realized_pnl"] > 0).sum()) if total else 0
        win_rate = wins / total if total else 0.0

        gross_profit = (
            float(closed.loc[closed["realized_pnl"] > 0, "realized_pnl"].sum()) if wins else 0.0
        )
        gross_loss = abs(float(closed.loc[closed["realized_pnl"] < 0, "realized_pnl"].sum()))
        profit_factor = gross_profit / gross_loss if gross_loss else 0.0

        avg_trade = float(closed["realized_pnl"].mean()) if total else 0.0
        expectancy = (avg_trade / initial_cash * 100) if initial_cash else 0.0

        return {
            "final_equity": Decimal(str(final_equity)),
            "total_return_percent": Decimal(str(total_return_pct)),
            "annualized_return_percent": Decimal(str(annualized)),
            "sharpe_ratio": Decimal(str(sharpe)),
            "max_drawdown_percent": Decimal(str(max_dd)),
            "win_rate": Decimal(str(win_rate)),  # fracción 0-1
            "profit_factor": Decimal(str(profit_factor)),
            "expectancy": Decimal(str(expectancy)),
            "total_trades": total,
            "average_trade_return": Decimal(str(avg_trade)),
        }
