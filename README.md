# Sistema de Trading Algorítmico

> **ADVERTENCIA**: Este proyecto es un marco de trabajo educativo y experimental. No garantiza rentabilidad. El trading con dinero real conlleva riesgo de pérdida total. El modo live está **deshabilitado por defecto** y requiere confirmación explícita.

## Estado

FASE 7 completada: el sistema incluye API REST, paper trading persistente, y módulo experimental de machine learning con regresión logística, feature engineering y estrategia ML. Todo sigue siendo simulado; no se ejecuta dinero real.

## Tecnologías

- Python 3.12+
- SQLAlchemy 2.0
- Pydantic Settings v2
- Alembic
- PostgreSQL (producción/pruebas) / SQLite (pruebas locales opcionales)
- Docker y Docker Compose
- FastAPI y Uvicorn
- NumPy (ML experimental)
- pytest

```text
app/
api/              API REST y panel (FASE 6)
brokers/          Adaptadores de broker (FASE 3)
config/           Configuración centralizada
          (app/config.py)
data/             Descarga y almacenamiento de datos (FASE 2)
database/         Modelos, sesiones y migraciones
indicators/       Indicadores técnicos (FASE 2)
models/           Modelos de dominio Pydantic (reservado)
risk/             Gestión de riesgo (FASE 3)
strategies/       Estrategias intercambiables (FASE 2)
execution/        Ejecución de órdenes (FASE 3)
backtesting/      Motor de backtesting (FASE 4)
paper_trading/    Paper trading persistente (FASE 5)
ml/               Machine learning experimental (FASE 7)
reporting/        Reportes (FASE 4)
services/         Servicios de alto nivel
utils/            Logging, seguridad y helpers
tests/            Pruebas
scripts/          Scripts auxiliares
docs/             Documentación detallada
docker/           Configuración Docker (en docker-compose.yml)
```

## Configuración rápida

1. Copia el archivo de entorno:

```powershell
copy .env.example .env
```

2. Revisa `.env`. Por defecto el sistema usa SQLite en desarrollo y PostgreSQL en Docker.

3. Instala dependencias (recomendado con entorno virtual):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

4. Ejecuta migraciones y pruebas:

```powershell
alembic upgrade head
pytest -v
```

## Uso con Docker

```powershell
docker compose up --build
```

Esto levanta PostgreSQL, aplica migraciones y ejecuta pytest.

## Comandos CLI

```powershell
# Ver estado y configuración segura
python -m app.cli health
python -m app.cli config

# Crear tablas sin Alembic (desarrollo)
python -m app.cli init-db
```

## Uso de datos y estrategia

```python
from datetime import date
from sqlalchemy.orm import Session

from app.data import YahooFinanceDataSource, MarketDataService, BarRepository
from app.database.session import SessionLocal
from app.strategies import TrendMomentumStrategy, TrendMomentumConfig

session: Session = SessionLocal()
source = YahooFinanceDataSource()
repository = BarRepository(session)
service = MarketDataService(source, repository)

df = service.get_historical_bars("SPY", date(2024, 1, 1), date(2024, 6, 1), "1d")

strategy = TrendMomentumStrategy(TrendMomentumConfig())
signal = strategy.generate_signal("SPY", df)
print(signal.signal_type, signal.explanation)
```

Para desarrollo/pruebas se puede usar `MockDataSource` en lugar de `YahooFinanceDataSource` para evitar llamadas de red.

## Backtesting

```python
from datetime import date
from decimal import Decimal

from app.backtesting import BacktestEngine
from app.brokers import MockBroker
from app.config import get_settings
from app.data import MockDataSource, MarketDataService
from app.database.session import SessionLocal
from app.execution import ExecutionEngine
from app.reporting import ReportGenerator
from app.risk import RiskManager
from app.strategies import TrendMomentumConfig, TrendMomentumStrategy

settings = get_settings()
session = SessionLocal()
broker = MockBroker(initial_cash=Decimal("100000"))
risk = RiskManager(settings)
execution = ExecutionEngine(broker, risk, session, settings)
strategy = TrendMomentumStrategy(TrendMomentumConfig())
engine = BacktestEngine(strategy, execution, session, initial_cash=Decimal("100000"))

source = MockDataSource()
service = MarketDataService(source)
df = service.get_historical_bars("SPY", date(2024, 1, 1), date(2024, 3, 1), "1d")

result = engine.run("SPY", df)
print(result.metrics)

report = ReportGenerator().generate_backtest_report(result.backtest_run, result.metrics)
print(report.summary)
```

## Ejecución de señales

```python
from app.brokers import MockBroker
from app.config import get_settings
from app.database.session import SessionLocal
from app.execution import ExecutionEngine
from app.risk import RiskManager

settings = get_settings()
session = SessionLocal()
broker = MockBroker(initial_cash=100_000)
risk = RiskManager(settings)
engine = ExecutionEngine(broker, risk, session, settings)

# signal es un SignalCreate generado por una estrategia
order = engine.process_signal(signal)
if order:
    print(f"Orden {order.broker_order_id} {order.status}")
else:
    print("Señal rechazada por riesgo o HOLD")
```

## Fases de desarrollo

- FASE 1: Estructura, configuración y base de datos (completada)
- FASE 2: Datos históricos, indicadores y estrategia (completada)
- FASE 3: RiskManager, broker mock y ejecución simulada (completada)
- FASE 4: Motor de backtesting y reportes (completada)
- FASE 5: Paper trading persistente y scheduler (completada)
- FASE 6: API FastAPI y panel de supervisión (completada)
- FASE 7: Módulo experimental de machine learning (completada)

## Paper trading

El scheduler ejecuta la estrategia periódicamente en modo paper, persistiendo señales, órdenes, posiciones y snapshots de cuenta.

```python
from decimal import Decimal

from app.brokers import MockBroker
from app.config import get_settings
from app.data import MarketDataService, MockDataSource
from app.database.session import SessionLocal
from app.paper_trading import PaperTradingScheduler
from app.risk import RiskManager
from app.strategies import TrendMomentumConfig, TrendMomentumStrategy

settings = get_settings()
strategy = TrendMomentumStrategy(TrendMomentumConfig())
data_service = MarketDataService(MockDataSource())
broker = MockBroker(initial_cash=settings.PAPER_TRADING_INITIAL_CASH)
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
# ... el scheduler ejecuta ticks periódicamente ...
scheduler.stop()
```

También desde la CLI:

```bash
trading paper-start    # inicia paper trading interactivo
trading paper-stop     # detiene paper trading
trading paper-status   # muestra estado
```

Variables de entorno relevantes:

- `PAPER_TRADING_ENABLED=false` por defecto; debe ser `true` para iniciar.
- `PAPER_TRADING_INTERVAL_SECONDS=3600` intervalo entre ticks.
- `PAPER_TRADING_LOOKBACK_DAYS=60` días de histórico por tick.
- `PAPER_TRADING_INITIAL_CASH=100000.00` efectivo inicial.

## API REST

El sistema expone una API REST con FastAPI para consultar todos los datos del sistema.

```bash
trading api-server --host 0.0.0.0 --port 8000
```

Endpoints disponibles:

- `GET /health` — estado del sistema
- `GET /api/strategy-runs` — lista de ejecuciones de estrategia
- `GET /api/strategy-runs/{id}` — detalle de una ejecución
- `GET /api/signals?symbol=AAPL&skip=0&limit=50` — señales con filtros
- `GET /api/orders?symbol=AAPL` — órdenes con filtros
- `GET /api/positions?status=open` — posiciones con filtros
- `GET /api/trades?symbol=AAPL` — trades con filtros
- `GET /api/backtests` — lista de backtests
- `GET /api/backtests/{id}` — detalle de un backtest
- `GET /api/snapshots?strategy_run_id=1` — snapshots de cuenta

Documentación interactiva en `http://localhost:8000/docs` (Swagger UI).

## Machine learning (experimental)

El módulo ML implementa una regresión logística con gradient descent (sin scikit-learn) para predecir la dirección del precio.

```bash
# Entrenar modelo
trading ml-train --symbol AAPL --forward-window 5

# Predecir
trading ml-predict --symbol AAPL --model-path models/AAPL_ml_model.json
```

Uso programático:

```python
from app.ml import MLPredictor, MLStrategy, MLStrategyConfig

# Entrenar
predictor = MLPredictor()
metrics = predictor.train(df, forward_window=5)
print(f"Accuracy: {metrics['train_accuracy']:.4f}")

# Predecir
result = predictor.predict(df)
print(f"Probabilidad: {result['probability']:.4f}")

# Usar como estrategia
strategy = MLStrategy(
    model=predictor.model,
    feature_engineer=predictor.feature_engineer,
    config=MLStrategyConfig(buy_threshold=0.6, sell_threshold=0.4),
)
signal = strategy.generate_signal("AAPL", df)
```

Features generados: EMA fast/slow, RSI, ATR, volumen relativo, retornos, SMA(20), ancho de Bollinger, histograma MACD, volatilidad histórica.

El modelo se persiste como JSON y se registra en BD como `ModelVersion` con status `experimental`.

## Dashboard web

El sistema incluye una interfaz web interactiva servida por FastAPI. No requiere comandos ni código.

### Script lanzador con interfaz CMD (recomendado)

```powershell
# Opción 1: Script Python con pre-flight checks y trace de errores
python run_server.py
python run_server.py --port 9000
python run_server.py --reload          # auto-reload en desarrollo
python run_server.py --host 0.0.0.0    # acceso externo

# Opción 2: Menú interactivo (Windows)
start_server.bat
```

El script `run_server.py` verifica dependencias, base de datos y `.env` antes de arrancar, y muestra errores con traceback formateado en color.

### Lanzamiento directo

```powershell
python -m app.cli api-server --host 127.0.0.1 --port 8080
```

Abrir `http://127.0.0.1:8080` en el navegador. El dashboard permite:

- **Resumen**: tarjetas con estado, cash, equity, PnL y posiciones abiertas
- **Señales**: tabla con filtros por símbolo
- **Órdenes**: historial de órdenes
- **Posiciones**: filtro por abiertas/cerradas
- **Trades**: historial de trades ejecutados
- **Backtests**: resultados de backtests
- **Paper Trading**: botones para iniciar/detener simulación
- **Machine Learning**: entrenar modelo desde la interfaz

Los datos se actualizan automáticamente cada 5 segundos.

## Seguridad

- Las credenciales se leen únicamente desde variables de entorno.
- Los logs enmascaran automáticamente `BROKER_API_KEY` y `BROKER_API_SECRET`.
- `LIVE_TRADING_ENABLED=false` por defecto.
- El sistema se niega a arrancar en modo `live` si no se habilita explícitamente.

## Licencia

MIT. Úsalo bajo tu propia responsabilidad.
