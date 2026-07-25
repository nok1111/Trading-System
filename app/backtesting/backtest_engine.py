"""Motor de backtesting barra a barra."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.database.models.backtest_run import BacktestRun
from app.execution.execution_engine import ExecutionEngine
from app.models.signal import SignalCreate
from app.reporting.metrics import MetricsCalculator
from app.strategies.strategy import Strategy


@dataclass
class BacktestResult:
    """Resultado de una corrida de backtesting."""

    backtest_run: BacktestRun
    equity_curve: pd.Series
    metrics: dict[str, Any]


class BacktestEngine:
    """Recorre datos históricos, ejecuta señales y calcula métricas."""

    def __init__(
        self,
        strategy: Strategy,
        execution_engine: ExecutionEngine,
        session: Session,
        initial_cash: Decimal = Decimal("100000.00"),
    ) -> None:
        self.strategy = strategy
        self.execution_engine = execution_engine
        self.session = session
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Decimal] = {}
        self._order_ids: list[int] = []

    def run(
        self,
        symbol: str,
        df: pd.DataFrame,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> BacktestResult:
        """Ejecuta el backtest completo para un símbolo."""
        df = df.sort_index()
        min_bars = self.strategy.min_bars
        if min_bars >= len(df):
            raise ValueError("Datos insuficientes para el backtest")

        equity_curve: dict[datetime, Decimal] = {df.index[0]: self.initial_cash}

        for i in range(min_bars, len(df)):
            snapshot = df.iloc[: i + 1]
            current_price = Decimal(str(df.iloc[i]["close"]))
            signal = self.strategy.generate_signal(
                symbol,
                snapshot,
                current_price=current_price,
                has_position=symbol in self.positions,
                position_entry_price=self.positions.get(symbol),
            )
            if signal.signal_type != "HOLD":
                order = self.execution_engine.process_signal(signal)
                if order is not None and order.status == "filled":
                    self._update_portfolio(order, current_price)
                    self._order_ids.append(order.id)
            equity_curve[df.index[i]] = self._equity(current_price)

        final_price = Decimal(str(df.iloc[-1]["close"]))
        self._close_open_positions(symbol, df.index[-1], final_price)

        equity_series = pd.Series(equity_curve, name="equity")
        trades_df = self._fetch_trades()
        start = start_date or df.index[0].date()
        end = end_date or df.index[-1].date()
        metrics = MetricsCalculator.calculate(
            equity_series, trades_df, float(self.initial_cash), start, end
        )
        backtest_run = self._save_backtest_run(symbol, start, end, metrics)
        return BacktestResult(
            backtest_run=backtest_run,
            equity_curve=equity_series,
            metrics=metrics,
        )

    def _update_portfolio(self, order, current_price: Decimal) -> None:
        qty = order.filled_quantity
        price = order.price or current_price
        if order.side == "BUY":
            self.cash -= qty * price
            self.positions[order.symbol] = self.positions.get(order.symbol, Decimal("0")) + qty
        elif order.side == "SELL":
            self.cash += qty * price
            self.positions[order.symbol] = self.positions.get(order.symbol, Decimal("0")) - qty
            if self.positions[order.symbol] <= 0:
                self.positions.pop(order.symbol, None)

    def _equity(self, current_price: Decimal) -> Decimal:
        position_value = sum(qty * current_price for qty in self.positions.values())
        return self.cash + position_value

    def _close_open_positions(
        self,
        symbol: str,
        timestamp: pd.Timestamp,
        current_price: Decimal,
    ) -> None:
        if symbol not in self.positions:
            return
        close_signal = SignalCreate(
            timestamp=timestamp.to_pydatetime(),
            symbol=symbol,
            signal_type="SELL",
            confidence=Decimal("1"),
            entry_price=current_price,
            strategy_name=self.strategy.name,
            explanation="Cierre al final del backtest",
        )
        order = self.execution_engine.process_signal(close_signal)
        if order is not None and order.status == "filled":
            self._update_portfolio(order, current_price)
            self._order_ids.append(order.id)

    def _fetch_trades(self) -> pd.DataFrame:
        if not self._order_ids:
            return pd.DataFrame(
                columns=["timestamp", "symbol", "side", "quantity", "price", "realized_pnl"]
            )
        from app.database.models.trade import Trade

        trades = self.session.query(Trade).where(Trade.order_id.in_(self._order_ids)).all()
        data = [
            {
                "timestamp": t.timestamp,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": float(t.quantity),
                "price": float(t.price),
                "realized_pnl": float(t.realized_pnl),
            }
            for t in trades
        ]
        return pd.DataFrame(data)

    def _save_backtest_run(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        metrics: dict[str, Any],
    ) -> BacktestRun:
        backtest_run = BacktestRun(
            strategy_name=self.strategy.name,
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date,
            initial_cash=self.initial_cash,
            final_equity=metrics["final_equity"],
            total_return_percent=metrics["total_return_percent"],
            annualized_return_percent=metrics["annualized_return_percent"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown_percent=metrics["max_drawdown_percent"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            expectancy=metrics["expectancy"],
            total_trades=metrics["total_trades"],
            avg_position_duration=None,
            avg_exposure=None,
            config={
                "initial_cash": str(self.initial_cash),
                "strategy": self.strategy.name,
            },
        )
        self.session.add(backtest_run)
        self.session.commit()
        return backtest_run
