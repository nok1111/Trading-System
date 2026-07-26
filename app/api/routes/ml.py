"""ML training endpoints."""

import threading
import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import app.api.state as state
from app.api.routes.trading import DbSession, PaginateSkip, PaginateLimit, SymbolQuery
from app.config import get_settings
from app.database.models import PredictionRecord
from app.database.session import SessionLocal

router = APIRouter(prefix="/api/ml", tags=["ml"])


class MLTrainRequest(BaseModel):
    """Payload para entrenar modelo ML."""
    symbol: str = "BTCUSDT"
    forward_window: int = 5
    threshold: float = 0.005
    timeframe: str = "1h"
    continuous: bool = False


@router.post("/train")
def ml_train(req: MLTrainRequest) -> dict:
    """Entrena un modelo ML en background con logs en tiempo real."""
    with state.ml_lock:
        if state.ml_status["is_training"]:
            raise HTTPException(status_code=409, detail="Ya hay un entrenamiento en curso")

    state.ml_cancel.clear()

    def _train_one():
        """Ejecuta una iteración completa de entrenamiento. Retorna (version_id, metrics, model_path)."""
        from datetime import UTC, date, datetime, timedelta
        from pathlib import Path

        from app.data import MarketDataService
        from app.database.models.model_version import ModelVersion
        from app.factories import create_data_source
        from app.ml import MLPredictor

        state.ml_log(f"Iniciando entrenamiento para {req.symbol} (timeframe={req.timeframe}, FW={req.forward_window})")
        state.ml_log("Creando predictor y feature engineer...")
        predictor = MLPredictor()
        state.ml_log(f"Features: {len(predictor.feature_engineer.FEATURE_COLUMNS)} columnas técnicas")
        state.ml_log(f"Algoritmo: {'LightGBM' if predictor.model._use_sklearn else 'LogisticRegression'}")

        state.ml_log("Conectando a Binance para descargar datos históricos (365 días)...")
        state.ml_status["progress"] = 10
        ds = MarketDataService(create_data_source(get_settings()))
        end = date.today()
        start = end - timedelta(days=365)
        df = ds.get_historical_bars(req.symbol, start, end, timeframe=req.timeframe)

        state.ml_log(f"Datos descargados: {len(df)} barras de {df.index[0] if len(df) > 0 else 'N/A'} a {df.index[-1] if len(df) > 0 else 'N/A'}")
        state.ml_status["progress"] = 30

        min_bars = predictor.feature_engineer.min_bars + 10
        if len(df) < min_bars:
            raise ValueError(f"Datos insuficientes: {len(df)} barras (mínimo {min_bars})")

        state.ml_log("Construyendo features técnicos (EMA, RSI, ATR, Bollinger, MACD, volatilidad...)...")
        state.ml_status["progress"] = 40
        x, y = predictor.feature_engineer.build_training_data(df, req.forward_window, req.threshold)
        state.ml_log(f"Dataset de entrenamiento: {len(x)} samples, {len(x.columns)} features")
        state.ml_log(f"Distribución de labels: BUY={int((y == 1).sum())}, SELL={int((y == 0).sum())}")

        state.ml_log("Entrenando modelo ML...")
        state.ml_status["progress"] = 60
        t0 = time.time()
        metrics = predictor.train(df, forward_window=req.forward_window, threshold=req.threshold)
        elapsed = time.time() - t0
        state.ml_log(f"Modelo entrenado en {elapsed:.1f}s")
        state.ml_log(f"Train Accuracy: {(metrics['train_accuracy'] * 100):.1f}% | Val Accuracy: {(metrics.get('val_accuracy', 0) * 100):.1f}%")
        state.ml_log(f"Algoritmo: {metrics.get('algorithm', 'unknown')} | Split: {metrics.get('train_size', 0)} train / {metrics.get('test_size', 0)} test")
        state.ml_log(f"Samples: {metrics['n_samples']}, Features: {metrics['n_features']}")
        state.ml_status["progress"] = 80

        state.ml_log("Guardando modelo a disco...")
        Path("models").mkdir(exist_ok=True)
        model_path = f"models/{req.symbol}_ml_model.json"
        predictor.save(model_path)
        state.ml_log(f"Modelo guardado en: {model_path}")

        state.ml_log("Registrando versión en base de datos...")
        state.ml_status["progress"] = 90
        db_session = SessionLocal()
        try:
            version = ModelVersion(
                name=f"{req.symbol}_lgbm",
                version=datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S"),
                path=model_path,
                metrics=metrics,
                status="experimental",
            )
            db_session.add(version)
            db_session.commit()
            db_session.refresh(version)
            version_id = version.id
        finally:
            db_session.close()

        state.ml_log(f"Entrenamiento completado. Version ID: {version_id}")
        return version_id, metrics, model_path

    def _train_worker():
        from datetime import UTC, datetime

        try:
            with state.ml_lock:
                state.ml_status["is_training"] = True
                state.ml_status["logs"] = []
                state.ml_status["result"] = None
                state.ml_status["error"] = None
                state.ml_status["started_at"] = datetime.now(tz=UTC).isoformat()
                state.ml_status["finished_at"] = None
                state.ml_status["symbol"] = req.symbol
                state.ml_status["progress"] = 0
                state.ml_status["continuous"] = req.continuous
                state.ml_status["loop_count"] = 0

            loop = 0
            while True:
                loop += 1
                with state.ml_lock:
                    state.ml_status["loop_count"] = loop
                if req.continuous:
                    state.ml_log(f"=== Ciclo continuo #{loop} ===")

                state.ml_status["progress"] = 0
                version_id, metrics, model_path = _train_one()

                state.ml_status["progress"] = 100
                with state.ml_lock:
                    state.ml_status["result"] = {
                        "status": "trained",
                        "model_version_id": version_id,
                        "metrics": metrics,
                        "path": model_path,
                        "loop": loop,
                    }

                if not req.continuous:
                    break

                if state.ml_cancel.is_set():
                    state.ml_log("Entrenamiento continuo cancelado por el usuario")
                    break

                state.ml_log("Esperando 5s antes del siguiente ciclo...")
                for _ in range(5):
                    if state.ml_cancel.is_set():
                        break
                    time.sleep(1)

                if state.ml_cancel.is_set():
                    state.ml_log("Entrenamiento continuo cancelado por el usuario")
                    break

                state.ml_log("Iniciando siguiente ciclo de entrenamiento...")

            with state.ml_lock:
                state.ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()
                state.ml_status["is_training"] = False
                state.ml_status["continuous"] = False
        except Exception as exc:
            state.ml_log(f"ERROR: {exc}")
            with state.ml_lock:
                state.ml_status["error"] = str(exc)
                state.ml_status["is_training"] = False
                state.ml_status["continuous"] = False
                state.ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()

    thread = threading.Thread(target=_train_worker, daemon=True)
    thread.start()
    return {"status": "started", "message": "Entrenamiento iniciado en background" + (" (continuo)" if req.continuous else "")}


@router.post("/cancel")
def ml_cancel() -> dict:
    """Cancela el entrenamiento ML en curso (incluye modo continuo)."""
    state.ml_cancel.set()
    return {"status": "cancel_requested"}


@router.post("/reset")
def ml_reset() -> dict:
    """Fuerza el reset del estado de entrenamiento (para entrenamientos atorados)."""
    from datetime import UTC, datetime
    state.ml_cancel.set()
    with state.ml_lock:
        state.ml_status["is_training"] = False
        state.ml_status["continuous"] = False
        state.ml_status["progress"] = 0
        state.ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()
    return {"status": "reset_ok"}


@router.get("/status")
def ml_status() -> dict:
    """Retorna el estado actual del entrenamiento ML con logs en tiempo real."""
    with state.ml_lock:
        return {
            "is_training": state.ml_status["is_training"],
            "logs": list(state.ml_status["logs"]),
            "result": state.ml_status["result"],
            "error": state.ml_status["error"],
            "started_at": state.ml_status["started_at"],
            "finished_at": state.ml_status["finished_at"],
            "symbol": state.ml_status["symbol"],
            "progress": state.ml_status["progress"],
            "continuous": state.ml_status["continuous"],
            "loop_count": state.ml_status["loop_count"],
        }


@router.get("/model-info")
def ml_model_info(db: DbSession) -> dict:
    """Info del modelo ML actual: última versión, métricas, algoritmo, features."""
    from app.database.models.model_version import ModelVersion

    version = (
        db.query(ModelVersion)
        .order_by(ModelVersion.id.desc())
        .first()
    )
    if not version:
        return {"has_model": False}
    m = version.metrics or {}
    return {
        "has_model": True,
        "id": version.id,
        "name": version.name,
        "version": version.version,
        "status": version.status,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "path": version.path,
        "algorithm": m.get("algorithm"),
        "train_accuracy": m.get("train_accuracy"),
        "val_accuracy": m.get("val_accuracy"),
        "n_samples": m.get("n_samples"),
        "n_features": m.get("n_features"),
        "forward_window": m.get("forward_window"),
        "threshold": m.get("threshold"),
        "live_accuracy": m.get("live_accuracy"),
        "live_evaluated": m.get("live_evaluated"),
    }


@router.get("/predictions")
def ml_predictions(
    db: DbSession,
    skip: PaginateSkip = 0,
    limit: PaginateLimit = 50,
    symbol: SymbolQuery = None,
) -> list[dict]:
    """Lista las predicciones ML registradas durante paper trading."""
    query = db.query(PredictionRecord)
    if symbol:
        query = query.filter(PredictionRecord.symbol == symbol.upper())
    records = query.order_by(PredictionRecord.id.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "symbol": r.symbol,
            "signal_type": r.signal_type,
            "probability": float(r.probability),
            "price_at_prediction": float(r.price_at_prediction),
            "evaluated": r.evaluated,
            "actual_direction": r.actual_direction,
            "correct": r.correct,
            "price_at_evaluation": float(r.price_at_evaluation) if r.price_at_evaluation else None,
            "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
            "strategy_run_id": r.strategy_run_id,
        }
        for r in records
    ]


@router.get("/accuracy")
def ml_accuracy(db: DbSession) -> dict:
    """Accuracy en vivo del modelo ML basado en predicciones evaluadas."""
    from sqlalchemy import and_, case, func

    rows = db.query(
        func.sum(case((PredictionRecord.evaluated == True, 1), else_=0)).label("total_evaluated"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.correct == True), 1), else_=0)).label("correct"),
        func.sum(case((PredictionRecord.evaluated == False, 1), else_=0)).label("pending"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "BUY", PredictionRecord.correct == True), 1), else_=0)).label("buy_correct"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "BUY"), 1), else_=0)).label("buy_total"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "SELL", PredictionRecord.correct == True), 1), else_=0)).label("sell_correct"),
        func.sum(case((and_(PredictionRecord.evaluated == True, PredictionRecord.signal_type == "SELL"), 1), else_=0)).label("sell_total"),
    ).one()

    total = int(rows.total_evaluated or 0)
    correct = int(rows.correct or 0)
    pending = int(rows.pending or 0)
    buy_total = int(rows.buy_total or 0)
    buy_correct = int(rows.buy_correct or 0)
    sell_total = int(rows.sell_total or 0)
    sell_correct = int(rows.sell_correct or 0)

    return {
        "total_evaluated": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else None,
        "pending": pending,
        "buy_accuracy": buy_correct / buy_total if buy_total > 0 else None,
        "buy_total": buy_total,
        "sell_accuracy": sell_correct / sell_total if sell_total > 0 else None,
        "sell_total": sell_total,
    }


@router.post("/retrain")
def ml_retrain(req: MLTrainRequest) -> dict:
    """Re-entrena el modelo con feedback de paper trading en background."""
    with state.ml_lock:
        if state.ml_status["is_training"]:
            raise HTTPException(status_code=409, detail="Ya hay un entrenamiento en curso")

    def _retrain_worker():
        from datetime import UTC, date, datetime, timedelta
        from pathlib import Path

        from app.data import MarketDataService
        from app.database.models.model_version import ModelVersion
        from app.factories import create_data_source
        from app.ml import MLPredictor

        try:
            with state.ml_lock:
                state.ml_status["is_training"] = True
                state.ml_status["logs"] = []
                state.ml_status["result"] = None
                state.ml_status["error"] = None
                state.ml_status["started_at"] = datetime.now(tz=UTC).isoformat()
                state.ml_status["finished_at"] = None
                state.ml_status["symbol"] = req.symbol
                state.ml_status["progress"] = 0

            state.ml_log(f"Iniciando RE-entrenamiento para {req.symbol} con feedback...")
            predictor = MLPredictor()
            state.ml_log(f"Algoritmo: {'LightGBM' if predictor.model._use_sklearn else 'LogisticRegression'}")

            state.ml_log("Descargando datos históricos (365 días)...")
            state.ml_status["progress"] = 10
            ds = MarketDataService(create_data_source(get_settings()))
            end = date.today()
            start = end - timedelta(days=365)
            df = ds.get_historical_bars(req.symbol, start, end, timeframe=req.timeframe)
            state.ml_log(f"Datos: {len(df)} barras")
            state.ml_status["progress"] = 30

            min_bars = predictor.feature_engineer.min_bars + 10
            if len(df) < min_bars:
                raise ValueError(f"Datos insuficientes: {len(df)} barras (mínimo {min_bars})")

            state.ml_log("Construyendo features y dataset...")
            state.ml_status["progress"] = 40
            x, y = predictor.feature_engineer.build_training_data(df, req.forward_window, req.threshold)
            state.ml_log(f"Dataset: {len(x)} samples, BUY={int((y == 1).sum())}, SELL={int((y == 0).sum())}")

            state.ml_log("Entrenando modelo...")
            state.ml_status["progress"] = 60
            t0 = time.time()
            metrics = predictor.train(df, forward_window=req.forward_window, threshold=req.threshold)
            elapsed = time.time() - t0
            state.ml_log(f"Modelo entrenado en {elapsed:.1f}s")
            state.ml_log(f"Train Accuracy: {(metrics['train_accuracy'] * 100):.1f}% | Val Accuracy: {(metrics.get('val_accuracy', 0) * 100):.1f}%")
            state.ml_log(f"Algoritmo: {metrics.get('algorithm', 'unknown')} | Split: {metrics.get('train_size', 0)} train / {metrics.get('test_size', 0)} test")

            state.ml_log("Evaluando accuracy en vivo desde paper trading...")
            state.ml_status["progress"] = 75
            db_session = SessionLocal()
            try:
                acc = ml_accuracy(db_session)
            finally:
                db_session.close()
            metrics["live_accuracy"] = acc["accuracy"]
            metrics["live_evaluated"] = acc["total_evaluated"]
            if acc["accuracy"] is not None:
                state.ml_log(f"Live Accuracy: {(acc['accuracy'] * 100):.1f}% ({acc['correct']}/{acc['total_evaluated']})")
            else:
                state.ml_log("Sin predicciones evaluadas aún para live accuracy")

            state.ml_log("Guardando modelo a disco...")
            state.ml_status["progress"] = 85
            Path("models").mkdir(exist_ok=True)
            model_path = f"models/{req.symbol}_ml_model.json"
            predictor.save(model_path)

            state.ml_log("Registrando versión en BD...")
            state.ml_status["progress"] = 95
            db_session = SessionLocal()
            try:
                version = ModelVersion(
                    name=f"{req.symbol}_lgbm_retrained",
                    version=datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S"),
                    path=model_path,
                    metrics=metrics,
                    status="experimental",
                )
                db_session.add(version)
                db_session.commit()
                db_session.refresh(version)
                version_id = version.id
            finally:
                db_session.close()

            state.ml_log(f"Re-entrenamiento completado. Version ID: {version_id}")
            state.ml_status["progress"] = 100
            with state.ml_lock:
                state.ml_status["result"] = {
                    "status": "retrained",
                    "model_version_id": version_id,
                    "metrics": metrics,
                    "live_accuracy": acc,
                    "path": model_path,
                }
                state.ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()
                state.ml_status["is_training"] = False
        except Exception as exc:
            state.ml_log(f"ERROR: {exc}")
            with state.ml_lock:
                state.ml_status["error"] = str(exc)
                state.ml_status["is_training"] = False
                state.ml_status["finished_at"] = datetime.now(tz=UTC).isoformat()

    thread = threading.Thread(target=_retrain_worker, daemon=True)
    thread.start()
    return {"status": "started", "message": "Re-entrenamiento iniciado en background"}
