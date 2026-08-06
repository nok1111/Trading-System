"""Generador de reportes de backtesting y trading."""

from dataclasses import dataclass
from typing import Any

from app.database.models.backtest_run import BacktestRun


@dataclass
class BacktestReport:
    """Reporte legible de una corrida de backtesting."""

    strategy_name: str
    symbols: list[str]
    total_trades: int
    total_return_percent: float
    max_drawdown_percent: float
    sharpe_ratio: float
    win_rate_percent: float
    profit_factor: float
    summary: str
    metrics: dict[str, Any]


class ReportGenerator:
    """Crea resúmenes a partir de BacktestRun y métricas."""

    def generate_backtest_report(
        self,
        backtest_run: BacktestRun,
        metrics: dict[str, Any] | None = None,
    ) -> BacktestReport:
        metrics = metrics or {}
        total_return = float(backtest_run.total_return_percent or 0)
        max_dd = float(backtest_run.max_drawdown_percent or 0)
        sharpe = float(backtest_run.sharpe_ratio or 0)
        win_rate_pct = float(backtest_run.win_rate or 0) * 100
        profit_factor = float(backtest_run.profit_factor or 0)
        trades = backtest_run.total_trades

        summary = (
            f"Backtest {backtest_run.strategy_name} sobre {backtest_run.symbols}: "
            f"retorno {total_return:.2f}%, "
            f"máx drawdown {max_dd:.2f}%, "
            f"Sharpe {sharpe:.2f}, "
            f"win rate {win_rate_pct:.1f}%, "
            f"profit factor {profit_factor:.2f}, "
            f"{trades} trades."
        )

        return BacktestReport(
            strategy_name=backtest_run.strategy_name,
            symbols=backtest_run.symbols,
            total_trades=trades,
            total_return_percent=total_return,
            max_drawdown_percent=max_dd,
            sharpe_ratio=sharpe,
            win_rate_percent=win_rate_pct,
            profit_factor=profit_factor,
            summary=summary,
            metrics=metrics,
        )
