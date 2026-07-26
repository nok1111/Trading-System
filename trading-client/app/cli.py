import argparse
import sys
from datetime import UTC, datetime

from app.config import get_settings
from app.data import MarketDataService
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.factories import create_broker, create_data_source
from app.paper_trading import PaperTradingScheduler
from app.risk import RiskManager
from app.strategies import TrendMomentumConfig, TrendMomentumStrategy
from app.utils.logging import configure_logging, get_logger
from app.utils.security import mask_secret

configure_logging()
logger = get_logger(__name__)

_scheduler_instance: PaperTradingScheduler | None = None


def cmd_health(args: argparse.Namespace) -> int:
    """Verifica que el sistema pueda arrancar sin errores fatales."""
    settings = get_settings()
    logger.info(
        "health_check",
        extra={
            "env": settings.APP_ENV,
            "trading_mode": settings.TRADING_MODE,
            "live_enabled": settings.LIVE_TRADING_ENABLED,
            "database_url": (
                settings.DATABASE_URL.split("@")[-1]
                if "@" in settings.DATABASE_URL
                else settings.DATABASE_URL
            ),
        },
    )
    print("OK")
    return 0


def cmd_init_db(args: argparse.Namespace) -> int:
    """Crea todas las tablas definidas en los modelos."""
    Base.metadata.create_all(bind=engine)
    logger.info(
        "database_initialized",
        extra={"tables": list(Base.metadata.tables.keys())},
    )
    print("Base de datos inicializada.")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Muestra la configuración activa, ocultando secretos."""
    settings = get_settings()
    safe = settings.to_safe_dict()
    for key, value in sorted(safe.items()):
        print(f"{key}={value}")
    print(f"BROKER_API_KEY_MASKED={mask_secret(settings.BROKER_API_KEY)}")
    print(f"BROKER_API_SECRET_MASKED={mask_secret(settings.BROKER_API_SECRET)}")
    return 0


def cmd_paper_start(args: argparse.Namespace) -> int:
    """Inicia el paper trading persistente."""
    global _scheduler_instance
    settings = get_settings()
    if not settings.PAPER_TRADING_ENABLED:
        logger.error("paper_trading_disabled")
        print("PAPER_TRADING_ENABLED no está activado.")
        return 1

    if settings.TRADING_MODE != "paper":
        print(f"Advertencia: TRADING_MODE={settings.TRADING_MODE}, se usará como paper.")

    data_service = MarketDataService(create_data_source(settings))
    broker = create_broker(settings)
    strategy = TrendMomentumStrategy(TrendMomentumConfig())
    risk = RiskManager(settings)

    scheduler = PaperTradingScheduler(
        settings=settings,
        strategy=strategy,
        data_service=data_service,
        broker=broker,
        risk_manager=risk,
        session_factory=SessionLocal,
    )
    run = scheduler.start()
    _scheduler_instance = scheduler

    logger.info(
        "paper_trading_started",
        extra={"run_id": run.id, "strategy": strategy.name, "symbols": settings.symbols_list},
    )
    print(f"Paper trading iniciado (run_id={run.id}). Presiona Enter para detener.")
    try:
        input()
    finally:
        scheduler.stop()
        print("Paper trading detenido.")
    return 0


def cmd_paper_stop(args: argparse.Namespace) -> int:
    """Detiene el paper trading en ejecución."""
    global _scheduler_instance
    if _scheduler_instance is None:
        print("No hay paper trading en ejecución.")
        return 1
    _scheduler_instance.stop()
    print("Paper trading detenido.")
    return 0


def cmd_paper_status(args: argparse.Namespace) -> int:
    """Muestra el estado del paper trading."""
    if _scheduler_instance is None:
        print("No hay paper trading en ejecución.")
    elif _scheduler_instance.is_running:
        print("Paper trading en ejecución.")
    else:
        print("Paper trading no está activo.")
    return 0


def cmd_api_server(args: argparse.Namespace) -> int:
    """Arranca el servidor API con uvicorn."""
    import uvicorn

    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8000)
    logger.info("api_server_starting", extra={"host": host, "port": port})
    print(f"Arrancando API en http://{host}:{port}")
    uvicorn.run("app.api.app:app", host=host, port=port, reload=False)
    return 0


def cmd_ml_train(args: argparse.Namespace) -> int:
    """Entrena un modelo ML y lo persiste."""
    from datetime import date, timedelta

    from app.data import MarketDataService
    from app.database.models.model_version import ModelVersion
    from app.factories import create_data_source
    from app.ml import MLPredictor

    predictor = MLPredictor()
    data_service = MarketDataService(create_data_source(get_settings()))

    end = date.today()
    start = end - timedelta(days=365)
    symbol = args.symbol
    timeframe = getattr(args, "timeframe", "1h")
    df = data_service.get_historical_bars(symbol, start, end, timeframe=timeframe)

    if len(df) < predictor.feature_engineer.min_bars + 10:
        print(f"Datos insuficientes para {symbol}: {len(df)} barras")
        return 1

    print(f"Entrenando {symbol} con {len(df)} barras ({timeframe})...")
    metrics = predictor.train(df, forward_window=args.forward_window, threshold=args.threshold)
    print(f"Modelo entrenado: accuracy={metrics['train_accuracy']:.4f}, samples={metrics['n_samples']}, algorithm={metrics.get('algorithm','?')}")

    model_path = f"models/{symbol}_ml_model.json"
    from pathlib import Path

    Path("models").mkdir(exist_ok=True)
    predictor.save(model_path)
    print(f"Modelo guardado en {model_path}")

    session = SessionLocal()
    try:
        version = ModelVersion(
            name=f"{symbol}_rf",
            version=datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S"),
            path=model_path,
            metrics=metrics,
            status="experimental",
        )
        session.add(version)
        session.commit()
        print(f"ModelVersion #{version.id} persistido con status=experimental")
    finally:
        session.close()
    return 0


def cmd_ml_predict(args: argparse.Namespace) -> int:
    """Carga un modelo ML y predice para un símbolo."""
    from datetime import date, timedelta

    from app.data import MarketDataService
    from app.factories import create_data_source
    from app.ml import MLPredictor

    predictor = MLPredictor.load(args.model_path)
    data_service = MarketDataService(create_data_source(get_settings()))
    end = date.today()
    start = end - timedelta(days=90)
    df = data_service.get_historical_bars(args.symbol, start, end)

    if len(df) < predictor.feature_engineer.min_bars:
        print(f"Datos insuficientes para {args.symbol}")
        return 1

    result = predictor.predict(df)
    print(f"Predicción para {args.symbol}:")
    print(f"  Probabilidad de subida: {result['probability']:.4f}")
    print(f"  Etiqueta: {result['prediction']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading",
        description="Sistema de trading algorítmico",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("health", help="Verificar estado del sistema")
    sub.add_parser("init-db", help="Crear tablas en la base de datos")
    sub.add_parser("config", help="Mostrar configuración activa")
    sub.add_parser("paper-start", help="Iniciar paper trading persistente")
    sub.add_parser("paper-stop", help="Detener paper trading persistente")
    sub.add_parser("paper-status", help="Ver estado del paper trading")
    api_parser = sub.add_parser("api-server", help="Arrancar servidor API")
    api_parser.add_argument("--host", default="0.0.0.0", help="Host de escucha")
    api_parser.add_argument("--port", type=int, default=8000, help="Puerto de escucha")
    ml_train_parser = sub.add_parser("ml-train", help="Entrenar modelo ML")
    ml_train_parser.add_argument("--symbol", default="AAPL", help="Símbolo a entrenar")
    ml_train_parser.add_argument("--forward-window", type=int, default=5, help="Barras hacia adelante")
    ml_train_parser.add_argument("--threshold", type=float, default=0.0, help="Umbral de etiqueta")
    ml_predict_parser = sub.add_parser("ml-predict", help="Predecir con modelo ML")
    ml_predict_parser.add_argument("--symbol", default="AAPL", help="Símbolo a predecir")
    ml_predict_parser.add_argument("--model-path", default="models/AAPL_ml_model.json", help="Ruta del modelo")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    command_func = globals().get(f"cmd_{args.command.replace('-', '_')}")
    if command_func is None:
        parser.print_help()
        return 1
    return command_func(args)


if __name__ == "__main__":
    sys.exit(main())
