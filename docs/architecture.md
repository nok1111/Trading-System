# Arquitectura del sistema

## Principios

- **Separación de responsabilidades**: cada dominio (datos, señales, riesgo, ejecución, broker, persistencia, reportes) vive en su propio módulo.
- **Adaptadores de infraestructura**: los brokers, fuentes de datos y bases de datos se acceden a través de interfaces. El dominio no conoce implementaciones.
- **Seguridad por defecto**: el modo live está bloqueado por configuración; las credenciales nunca se loguean en texto plano.
- **Observabilidad**: todas las decisiones, rechazos, errores y eventos de sistema se registran en base de datos.
- **Testabilidad**: cada componente puede probarse en aislamiento con adaptadores mock.

## Flujo de datos

```text
Mercado -> DataService -> Indicadores -> Estrategia -> Señal
                                            |
                                            v
RiskManager -> OrderExecutor -> BrokerAdapter -> Base de datos
```

## Capas

### 1. Adquisición de datos (`app/data/`)

Responsable de descargar OHLCV, normalizar zonas horarias, validar duplicados y guardar en `MarketBar`.

### 2. Indicadores (`app/indicators/`)

Implementaciones propias de SMA, EMA, RSI, MACD, ATR, VWAP, Bollinger Bands, retornos y volatilidad.

### 3. Estrategias (`app/strategies/`)

Interfaz `Strategy` con `prepare_data`, `generate_signal`, `calculate_confidence` y `explain_signal`. La primera implementación será `TrendMomentumStrategy`.

### 4. Gestión de riesgo (`app/risk/`)

`RiskManager` evalúa cada señal contra límites de posición, riesgo por operación, pérdida diaria, exposición, spreads y circuit breakers. Puede rechazar operaciones.

### 5. Ejecución (`app/execution/`)

`OrderExecutor` convierte señales aceptadas en órdenes, genera `client_order_id` únicos, maneja reintentos e idempotencia.

### 6. Brokers (`app/brokers/`)

Interfaz `BrokerAdapter`. Implementaciones:

- `MockBrokerAdapter`: para pruebas unitarias.
- `PaperBrokerAdapter`: simulación con datos de mercado.
- Adaptadores reales: Alpaca, Interactive Brokers, etc., nunca habilitados por defecto.

### 7. Persistencia (`app/database/`)

SQLAlchemy 2.0 + Alembic. Modelos:

- `MarketBar`
- `Signal`
- `Order`
- `Trade`
- `Position`
- `AccountSnapshot`
- `StrategyRun`
- `BacktestRun`
- `RiskEvent`
- `SystemEvent`
- `ModelVersion`

### 8. Reportes (`app/reporting/`)

Generación de métricas, equity curve, drawdown y reportes HTML/CSV.

### 9. API y panel (`app/api/`)

FastAPI con endpoints REST y una interfaz web sencilla.

## Decisiones técnicas actuales

- **SQLAlchemy sincrónico**: simplifica transacciones y pruebas en FASE 1. Se puede evolucionar a async más adelante si es necesario.
- **Pydantic Settings v2**: centraliza validación y lectura desde `.env`.
- **JSON genérico**: campos de metadatos usan `JSON` de SQLAlchemy, compatible con PostgreSQL y SQLite.
- **Decimal para precios**: evita errores de redondeo en dinero y cantidades.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Ejecución accidental en live | `LIVE_TRADING_ENABLED=false` por defecto + validador Pydantic |
| Fuga de credenciales en logs | Filtro de redacción en logger |
| Datos corruptos o duplicados | Constraints únicos y validación en DataService |
| Look-ahead bias en backtesting | Motor de eventos cronológico (FASE 4) |
| Pérdidas diarias excesivas | Límites configurables y circuit breaker (FASE 3) |
