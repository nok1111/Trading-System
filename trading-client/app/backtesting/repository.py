"""Repositorio para persistir resultados de backtesting."""

from sqlalchemy.orm import Session

from app.database.models.backtest_run import BacktestRun


class BacktestRepository:
    """Acceso a BacktestRun en base de datos."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, backtest_run: BacktestRun) -> BacktestRun:
        self.session.add(backtest_run)
        self.session.commit()
        self.session.refresh(backtest_run)
        return backtest_run

    def get(self, backtest_run_id: int) -> BacktestRun | None:
        return self.session.get(BacktestRun, backtest_run_id)
