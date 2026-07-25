"""Pruebas de la API REST (FASE 6)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.app import app, get_db
from app.database.base import Base
from app.database.models import *  # noqa: F401, F403


@pytest.fixture(scope="class")
def api_engine() -> Engine:
    """Motor SQLite en memoria compartible entre hilos para tests de API."""
    engine = create_engine(
        "sqlite://",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="class")
def api_client(api_engine: Engine) -> TestClient:
    """Cliente de test con get_db override usando el engine en memoria."""

    def _get_test_db() -> Session:
        session = Session(bind=api_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestApi:
    def test_health(self, api_client: TestClient) -> None:
        response = api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "trading_mode" in data
        assert "live_trading_enabled" in data

    def test_list_strategy_runs_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/strategy-runs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_strategy_run_not_found(self, api_client: TestClient) -> None:
        response = api_client.get("/api/strategy-runs/99999")
        assert response.status_code == 404

    def test_list_signals_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/signals")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_signals_with_symbol_filter(self, api_client: TestClient) -> None:
        response = api_client.get("/api/signals?symbol=AAPL")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_orders_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_positions_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/positions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_positions_with_status_filter(self, api_client: TestClient) -> None:
        response = api_client.get("/api/positions?status=open")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_trades_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/trades")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_backtests_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/backtests")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_backtest_not_found(self, api_client: TestClient) -> None:
        response = api_client.get("/api/backtests/99999")
        assert response.status_code == 404

    def test_list_snapshots_empty(self, api_client: TestClient) -> None:
        response = api_client.get("/api/snapshots")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_snapshots_with_run_filter(self, api_client: TestClient) -> None:
        response = api_client.get("/api/snapshots?strategy_run_id=1")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_params(self, api_client: TestClient) -> None:
        response = api_client.get("/api/signals?skip=0&limit=10")
        assert response.status_code == 200

    def test_dashboard_html(self, api_client: TestClient) -> None:
        response = api_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Trading System" in response.text

    def test_paper_trading_status(self, api_client: TestClient) -> None:
        response = api_client.get("/api/paper-trading/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("running", "stopped")

    def test_paper_trading_stop_when_not_running(self, api_client: TestClient) -> None:
        response = api_client.post("/api/paper-trading/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "not_running"

    def test_ml_train(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/ml/train",
            json={"symbol": "AAPL", "forward_window": 5, "threshold": 0.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "trained"
        assert "model_version_id" in data
        assert "metrics" in data
