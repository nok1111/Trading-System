"""Pruebas del módulo ML (FASE 7)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.data import MockDataSource
from app.ml import FeatureEngineer, MLModel, MLPredictor, MLStrategy, MLStrategyConfig


def _make_ohlcv(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Genera DataFrame OHLCV sintético."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    trend = np.cumsum(rng.normal(0.01, 0.5, n))
    close = 100.0 + trend
    open_ = close + rng.normal(0, 0.2, n)
    high = np.maximum(open_, close) + rng.uniform(0, 0.5, n)
    low = np.minimum(open_, close) - rng.uniform(0, 0.5, n)
    volume = rng.integers(1_000_000, 10_000_000, n)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "timestamp"
    return df


class TestFeatureEngineer:
    def test_prepare_features_adds_columns(self) -> None:
        df = _make_ohlcv(100)
        fe = FeatureEngineer()
        data = fe.prepare_features(df)
        for col in fe.FEATURE_COLUMNS:
            assert col in data.columns

    def test_build_training_data(self) -> None:
        df = _make_ohlcv(100)
        fe = FeatureEngineer()
        x, y = fe.build_training_data(df, forward_window=5)
        assert len(x) > 0
        assert len(x) == len(y)
        assert set(x.columns) == set(fe.FEATURE_COLUMNS)
        assert y.isin([0, 1]).all()

    def test_extract_latest_features(self) -> None:
        df = _make_ohlcv(100)
        fe = FeatureEngineer()
        features = fe.extract_latest_features(df)
        assert len(features) == 1
        assert set(features.columns) == set(fe.FEATURE_COLUMNS)


class TestMLModel:
    def test_fit_and_predict(self) -> None:
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, (200, 5))
        y = (x[:, 0] > 0).astype(int)
        model = MLModel(learning_rate=0.1, max_iterations=300)
        metrics = model.fit(x, y, feature_names=["a", "b", "c", "d", "e"])
        assert metrics["train_accuracy"] > 0.7
        assert model.is_trained
        preds = model.predict(x)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_predict_untrained_raises(self) -> None:
        model = MLModel()
        with pytest.raises(RuntimeError, match="no entrenado"):
            model.predict(np.array([[1, 2]]))

    def test_serialization(self) -> None:
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, (50, 3))
        y = (x[:, 0] > 0).astype(int)
        model = MLModel()
        model.fit(x, y, feature_names=["a", "b", "c"])
        data = model.to_dict()
        restored = MLModel.from_dict(data)
        assert restored.is_trained
        np.testing.assert_array_almost_equal(restored.weights, model.weights)
        assert restored.bias == model.bias
        assert restored.feature_names == model.feature_names


class TestMLPredictor:
    def test_train_and_predict(self) -> None:
        df = _make_ohlcv(150)
        predictor = MLPredictor()
        metrics = predictor.train(df, forward_window=5)
        assert "train_accuracy" in metrics
        assert predictor.model.is_trained

        result = predictor.predict(df)
        assert "probability" in result
        assert "prediction" in result
        assert 0 <= result["probability"] <= 1
        assert result["prediction"] in (0, 1)

    def test_predict_untrained_raises(self) -> None:
        df = _make_ohlcv(100)
        predictor = MLPredictor()
        with pytest.raises(RuntimeError, match="no entrenado"):
            predictor.predict(df)

    def test_save_and_load(self, tmp_path) -> None:
        df = _make_ohlcv(150)
        predictor = MLPredictor()
        predictor.train(df)
        path = tmp_path / "model.json"
        predictor.save(path)
        loaded = MLPredictor.load(path)
        assert loaded.model.is_trained
        result = loaded.predict(df)
        assert "probability" in result


class TestMLStrategy:
    def test_strategy_with_trained_model(self) -> None:
        df = _make_ohlcv(150)
        predictor = MLPredictor()
        predictor.train(df)
        strategy = MLStrategy(
            model=predictor.model,
            feature_engineer=predictor.feature_engineer,
            config=MLStrategyConfig(buy_threshold=0.5, sell_threshold=0.5),
        )
        signal = strategy.generate_signal("AAPL", df)
        assert signal.signal_type in ("BUY", "SELL", "HOLD")
        assert signal.strategy_name == "MLStrategy"

    def test_strategy_untrained_returns_hold(self) -> None:
        df = _make_ohlcv(100)
        model = MLModel()
        strategy = MLStrategy(model=model)
        signal = strategy.generate_signal("AAPL", df)
        assert signal.signal_type == "HOLD"

    def test_strategy_min_bars(self) -> None:
        model = MLModel()
        strategy = MLStrategy(model=model)
        assert strategy.min_bars > 0

    def test_strategy_with_mock_data_source(self) -> None:
        from app.data import MarketDataService

        ds = MarketDataService(MockDataSource())
        end = date.today()
        start = end - timedelta(days=365)
        df = ds.get_historical_bars("AAPL", start, end)

        predictor = MLPredictor()
        predictor.train(df)
        strategy = MLStrategy(
            model=predictor.model,
            feature_engineer=predictor.feature_engineer,
        )
        signal = strategy.generate_signal("AAPL", df)
        assert signal.signal_type in ("BUY", "SELL", "HOLD")
