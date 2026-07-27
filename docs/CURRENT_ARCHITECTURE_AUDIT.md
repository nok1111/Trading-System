# Auditoría de Arquitectura Actual

> **Fecha**: 2025-01  
> **Propósito**: Documentar exactamente cómo está construido el proyecto hoy, con rutas y líneas reales, antes de cualquier cambio.  
> **Alcance**: `trading-client/` (cliente activo), `auth-server/` (VPS), `app/` (legacy), `desktop/` (Tauri).

---

## 1. Componentes y Stack

| Componente | Ruta | Stack | Rol |
|---|---|---|---|
| **Cliente activo** | `trading-client/app` | Python 3.12, FastAPI, SQLAlchemy 2, SQLite, httpx | API local en `127.0.0.1:18652`; broker, agente IA, ejecución, datos de mercado |
| **Escritorio** | `trading-client/desktop` | Tauri 2 + Rust, React 19, Vite 7, Tailwind 4, recharts | UI; `src-tauri/src/lib.rs` lanza `uvicorn app.api.app:app` como proceso hijo |
| **Auth Server (VPS)** | `auth-server/` | FastAPI, PostgreSQL (SQLite en dev), PyJWT, Binance Pay | Login, suscripciones, licencia JWT, grants de cuota de IA |
| **Monolito legacy** | `app/` + `tests/` | Igual que el cliente | Casi duplicado del cliente; **única** suite de tests actual |

---

## 2. Mapa del Repositorio

```
TRADING PROJECT/
├── app/                          # Legacy monolith (congelado, NO se borra)
│   └── tests/                    # Única suite de tests existente
├── auth-server/                  # Auth Server (VPS)
│   ├── app/
│   │   ├── config.py             # JWT_SECRET="change-me-in-production", CORS="*"
│   │   ├── database/models/      # User, AIUsageLog, Payment
│   │   ├── routes/ai_grant.py    # Grant JWT 5min, single-use, cuota diaria
│   │   ├── services/rate_limit.py # Plan limits: free/pro/premium
│   │   └── ...
│   └── ...
├── trading-client/               # Cliente activo (fuente de verdad)
│   ├── app/
│   │   ├── ai/agent.py           # 864 líneas, AITradingAgent (buy-only + auto-close)
│   │   ├── api/
│   │   │   ├── helpers.py        # resolve_binance_keys, get_shared_broker
│   │   │   ├── routes/ai_agent.py # /api/ai-agent/*, /api/binance/balance
│   │   │   ├── routes/trading.py  # /api/positions (refresco precio Binance)
│   │   │   ├── routes/market.py   # /api/market/movers, /klines, /smart-money
│   │   │   └── ...
│   │   ├── brokers/
│   │   │   ├── broker.py         # ABC delgado: place_order, cancel_order, get_order, get_account, get_quote
│   │   │   ├── binance_broker.py # BinanceBroker: HMAC-SHA256, httpx sync
│   │   │   └── mock_broker.py    # MockBroker para paper trading
│   │   ├── config.py             # Settings (Pydantic), BROKER_PROVIDER enum
│   │   ├── data/
│   │   │   ├── binance_source.py # BinanceDataSource: klines, top movers
│   │   │   ├── price_stream.py   # WebSocket Binance, background thread
│   │   │   ├── binance_leaderboard.py # Smart Money (Binance Futures leaderboard)
│   │   │   └── ...
│   │   ├── database/models/      # 14 modelos SQLAlchemy (ver §5)
│   │   ├── execution/execution_engine.py # ExecutionEngine: señal → orden → trade → posición
│   │   ├── risk/risk_manager.py  # RiskManager: evalúa señales, calcula position size
│   │   ├── services/
│   │   │   ├── auth.py           # LocalUser dataclass, get_current_user
│   │   │   ├── crypto.py         # Fernet encrypt/decrypt (clave derivada de AUTH_SERVER_URL)
│   │   │   └── license.py        # validate_license, request_ai_grant, report_ai_usage
│   │   ├── factories.py          # create_broker(), create_data_source()
│   │   └── ...
│   ├── desktop/
│   │   ├── src-tauri/src/lib.rs  # spawn_python_backend(), unsafe static mut
│   │   └── src/                  # React 19 + Vite 7 + Tailwind 4
│   └── ...
├── docs/                         # Documentación (architecture.md e install.md obsoletos)
├── .env                          # Secretos en claro (ver SECURITY_REVIEW.md)
├── trading.db                    # BD SQLite con datos reales
└── README.md                     # Describe el monolito legacy
```

---

## 3. Flujos Reales

### 3.1 Login / Licencia

1. El frontend React envía credenciales a `auth-server` → recibe JWT.
2. Cada request al trading-client incluye el JWT en `Authorization: Bearer`.
3. El middleware del trading-client llama a `validate_license()` (`trading-client/app/services/license.py:15`) que hace `POST /api/license/validate` al auth-server.
4. El auth-server valida el JWT, devuelve `{valid, user_id, email, subscription, plan_limits}`.
5. El middleware adjunta esto a `request.state.user`.
6. `get_current_user()` (`trading-client/app/services/auth.py:41`) construye un `LocalUser` **sin** poblar los campos `ai_*_enc` ni `binance_api_key_enc` — siempre son `None`.

### 3.2 Conexión Binance

1. `resolve_binance_keys()` (`trading-client/app/api/helpers.py:10`) resuelve claves en orden:
   - `user_settings` table (encriptadas con Fernet) → decrypt
   - `current_user.binance_api_key_enc` (siempre `None` por el bug de `get_current_user`)
   - `.env` (`BROKER_API_KEY` / `BROKER_API_SECRET`)
2. `get_shared_broker()` (`trading-client/app/api/helpers.py:57`) crea un `BinanceBroker` o `MockBroker` según `TRADING_MODE` y `LIVE_TRADING_ENABLED`.
3. `BinanceBroker` (`trading-client/app/brokers/binance_broker.py:38`) firma requests con HMAC-SHA256 vía `_signed_request()` (línea 313).
4. `create_broker()` (`trading-client/app/factories.py:23`) decide: si `BROKER_PROVIDER=binance` y `is_live` → `BinanceBroker`; si no → `MockBroker`.

### 3.3 Ciclo del Agente IA → Señal → Orden

1. `AITradingAgent.start()` (`trading-client/app/ai/agent.py:109`) lanza dos threads daemon:
   - **Thread de análisis** (`_run_loop`, línea 149): cada `interval` segundos:
     1. `_request_grant()` (línea 327) → `POST /api/ai/authorize` al auth-server.
     2. Si grant OK, `_tick()` (línea 371):
        - `_gather_context()` (línea 500) llama a su propia API HTTP (`/api/snapshots`, `/api/positions`, `/api/market/movers`, `/api/prices/live`, `/api/risk-events`).
        - `_ask_llm()` (línea 598) envía contexto + `SYSTEM_PROMPT` (buy-only) al LLM (Groq → Gemini → Ollama fallback).
        - Ejecuta acciones: `_execute_action()` → `POST /api/ai-agent/execute`.
     3. `_report_usage()` (línea 348) → `POST /api/ai/report` al auth-server.
   - **Thread de auto-close** (`_auto_close_loop`, línea 185): cada 5 segundos:
     - `_check_auto_close()` (línea 194) consulta `/api/positions?status=open`.
     - Obtiene precio actual de Binance con `httpx.get` directo (líneas 219-233).
     - Lógica de trailing stop en `float` (líneas 237-323).
     - Si stop-loss o take-profit hit → `POST /api/ai-agent/execute` con `action_type: "sell"`.

2. `POST /api/ai-agent/execute` (`trading-client/app/api/routes/ai_agent.py:501`):
   - Resuelve claves, obtiene `broker` compartido.
   - Obtiene precio live de Binance (spot → futures fallback) con `httpx.get` directo (líneas 568-587).
   - Crea `SignalCreate` → `ExecutionEngine.process_signal()`.
   - `ExecutionEngine` (`trading-client/app/execution/execution_engine.py:43`):
     - Persiste señal, evalúa riesgo con `RiskManager`.
     - Si BUY: calcula cantidad, crea `Order`, llama `broker.place_order()`.
     - Si SELL: busca posición abierta, crea `Order`, llama `broker.place_order()`.
     - Persiste `Trade` y `Position` en SQLite.

---

## 4. Acoplamiento con Binance (Inventario Exhaustivo)

### 4.1 Adaptador formal

| Fichero | Líneas | Descripción |
|---|---|---|
| `trading-client/app/brokers/broker.py` | 1-37 | ABC `Broker` con 5 métodos. Devuelve modelos ORM (`Order`, `AccountSnapshot`), no modelos de dominio. |
| `trading-client/app/brokers/binance_broker.py` | 1-387 | `BinanceBroker`: firma HMAC, `exchangeInfo` cache, `place_order`, `place_stop_loss`, `place_take_profit`, `cancel_order`, `get_order`, `get_account`, `get_quote`. |
| `trading-client/app/brokers/mock_broker.py` | — | `MockBroker` para paper trading. |
| `trading-client/app/factories.py` | 23-44 | `create_broker()`: único `if provider == "binance"`. |

### 4.2 Llamadas crudas a Binance fuera del adaptador

| Fichero | Líneas | Endpoint / URL | Propósito |
|---|---|---|---|
| `trading-client/app/api/routes/ai_agent.py` | 319 | `import httpx as _httpx` | Balance directo |
| | 338 | `broker._signed_request("GET", "/api/v3/account")` | Saldos de Binance |
| | 349 | `api.binance.com/api/v3/ticker/price?symbol=USDTMXN` | Tipo de cambio MXN |
| | 372 | `api.binance.com/api/v3/ticker/price?symbol=EURUSDT` | Conversión EUR→USD |
| | 382-388 | `api.binance.com/api/v3/ticker/price?symbol={asset}USDT` | Precio de cada activo |
| | 568-585 | `api.binance.com/api/v3/ticker/price?symbol={symbol}` + `fapi.binance.com/fapi/v1/ticker/price` | Precio live para ejecución |
| `trading-client/app/api/routes/trading.py` | 157-175 | `api.binance.com/api/v3/ticker/price?symbol={pos.symbol}` + `fapi.binance.com/fapi/v1/ticker/price` | Refresco de precio en `/api/positions` |
| `trading-client/app/api/routes/market.py` | 105-107 | `api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}` | Klines OHLCV |
| `trading-client/app/ai/agent.py` | 219-233 | `api.binance.com/api/v3/ticker/price?symbol={symbol}` + `fapi.binance.com/fapi/v1/ticker/price` | Precio para auto-close |
| `trading-client/app/data/binance_source.py` | 95-98 | `api.binance.com/api/v3/klines` | Descarga de velas OHLCV |
| | 168-173 | `api.binance.com/api/v3/ticker/24hr` o `fapi.binance.com/fapi/v1/ticker/24hr` | Top movers 24h |
| `trading-client/app/data/price_stream.py` | 16-17 | `wss://stream.binance.com:9443/stream` / `wss://testnet.binance.vision/stream` | WebSocket precios en tiempo real |
| `trading-client/app/data/binance_leaderboard.py` | — | Binance Futures leaderboard API | Smart Money |

### 4.3 Condicionales dispersos por nombre de broker

| Fichero | Línea | Código |
|---|---|---|
| `trading-client/app/api/helpers.py` | 10 | `def resolve_binance_keys(...)` — nombre hardcodea Binance |
| `trading-client/app/factories.py` | 16 | `if provider == "binance":` |
| `trading-client/app/factories.py` | 18 | `if provider in ("alpaca", "ibkr"):` |
| `trading-client/app/factories.py` | 33 | `if provider == "binance" and is_live:` |
| `trading-client/app/api/routes/ai_agent.py` | 322 | `if settings.BROKER_PROVIDER != "binance":` |
| `trading-client/app/api/routes/ai_agent.py` | 438 | `is_binance = settings.BROKER_PROVIDER == "binance" and bool(keys)` |
| `trading-client/app/api/routes/ai_agent.py` | 523 | `is_binance_broker = settings.BROKER_PROVIDER == "binance" and bool(keys)` |

### 4.4 Configuración

- `trading-client/app/config.py:30`: `BROKER_PROVIDER: Literal["mock", "paper", "alpaca", "ibkr", "binance"] = "mock"` — `alpaca` e `ibkr` enumerados pero sin implementación.

---

## 5. Inventario de Tablas

### 5.1 Trading Client (`trading-client/app/database/models/`)

14 modelos SQLAlchemy:

| Modelo | Fichero | Tabla | Propósito |
|---|---|---|---|
| `AccountSnapshot` | `account_snapshot.py` | `account_snapshots` | Snapshot de cuenta (cash, equity, PnL) |
| `BacktestRun` | `backtest_run.py` | `backtest_runs` | Resultados de backtests |
| `MarketBar` | `market_bar.py` | `market_bars` | Velas OHLCV cacheadas |
| `ModelVersion` | `model_version.py` | `model_versions` | Versiones de modelos ML |
| `Order` | `order.py` | `orders` | Órdenes enviadas al broker |
| `Position` | `position.py` | `positions` | Posiciones abiertas/cerradas |
| `PredictionRecord` | `prediction_record.py` | `prediction_records` | Predicciones ML |
| `RiskEvent` | `risk_event.py` | `risk_events` | Eventos de riesgo (rechazos, alerts) |
| `Signal` | `signal.py` | `signals` | Señales de trading |
| `StrategyRun` | `strategy_run.py` | `strategy_runs` | Ejecuciones de estrategias |
| `SystemEvent` | `system_event.py` | `system_events` | Eventos de sistema |
| `Trade` | `trade.py` | `trades` | Trades ejecutados |
| `UserSettings` | `user_settings.py` | `user_settings` | API keys encriptadas por usuario |
| *(sin User)* | — | — | El trading-client no tiene modelo User; usa `LocalUser` dataclass |

**Campos monetarios**: `Order.quantity`, `Order.filled_quantity`, `Order.price` → `Numeric(19, 8)` / `Decimal`. `Position` igual. `AccountSnapshot` igual. **Pero** el código que los lee/escribe usa `float` en多处 (ver §6).

### 5.2 Auth Server (`auth-server/app/database/models/`)

| Modelo | Fichero | Tabla | Propósito |
|---|---|---|---|
| `User` | `user.py` | `users` | Usuarios (email, password hash, subscription) — **sin** API keys |
| `AIUsageLog` | `ai_usage.py` | `ai_usage_logs` | Cuota diaria de IA por usuario |
| `Payment` | `payment.py` | `payments` | Pagos vía Binance Pay |

---

## 6. Duplicación `app/` vs `trading-client/app/`

El directorio `app/` en la raíz es una copia casi exacta del trading-client. Es el monolito original antes de que se extrajera el cliente. Diferencias detectadas:

- `app/` tiene su propia suite de tests (`tests/`) — la única que existe.
- `trading-client/app/` tiene `services/license.py`, `services/auth.py` (LocalUser), middleware de licencia — el monolito no.
- `trading-client/app/` tiene `database/models/user_settings.py` — el monolito puede no tenerlo.
- `trading-client/desktop/` no existe en el monolito.

**Decisión**: `trading-client/` es la fuente de verdad. `app/` se congela como legacy.

---

## 7. IA Local — Estado Actual

### 7.1 `AITradingAgent` (`trading-client/app/ai/agent.py`, 864 líneas)

- **Un solo archivo**, una sola clase.
- **System prompt** hardcodeado (línea 26): buy-only, devuelve JSON con `actions`.
- **Proveedores**: Groq, Gemini, Ollama, OpenAI-compatibles (deepseek, mistral, together, perplexity, grok). Cadena de fallback Groq→Gemini→Ollama.
- **`_gather_context()`** (línea 500): llama a su propia API HTTP via `_api_get()`. No accede a BD directamente.
- **`_ask_llm()`** (línea 598): inyecta contexto como string JSON en el mensaje del usuario. Sin validación de esquema de salida.
- **`_check_auto_close()`** (línea 194):
  - Ejecuta **ventas reales** cada 5 segundos.
  - Lógica de trailing stop en `float` (líneas 237-323).
  - No pasa por el Risk Engine.
  - Llama a `POST /api/ai-agent/execute` con `action_type: "sell"`.
- **Grant system**: `_request_grant()` (línea 327) y `_report_usage()` (línea 348) via `services/license.py`.

### 7.2 Auth Server — Grant y Cuota

- `auth-server/app/routes/ai_grant.py` (264 líneas):
  - `POST /api/ai/authorize`: emite grant JWT de 5 min, single-use (en memoria).
  - `POST /api/ai/report`: consume el grant, incrementa `AIUsageLog`.
  - `GET /api/ai/quota`: consulta cuota sin consumir.
- `auth-server/app/services/rate_limit.py`: plan limits (free: 50/day, pro: 500/day, premium: 99999/day).

---

## 8. Dinero en `float` (Problema)

| Fichero | Líneas | Uso |
|---|---|---|
| `trading-client/app/ai/agent.py` | 224, 237-257, 287, 307, 317 | Trailing stop, PnL, peak tracking |
| `trading-client/app/api/routes/ai_agent.py` | 344, 358-359, 365, 388, 406-407, 411-417 | Balance, USD value, MXN conversion |
| `trading-client/app/api/routes/trading.py` | 168, 175-178 | Precio live en `/api/positions` |
| `trading-client/app/api/routes/market.py` | 113-117 | Klines OHLCV como `float` |
| `trading-client/app/data/binance_source.py` | 134-138, 186-188 | Parseo de klines y movers como `float` |

---

## 9. Evaluación: Qué Conservar / Refactorizar / Reemplazar

### Conservar (funciona y es buena base)

- **HMAC-SHA256 signing** en `BinanceBroker._signed_request()` — reutilizar por composición.
- **Cache de `exchangeInfo`** en `BinanceBroker._symbol_filters_cache` — reutilizar.
- **Grant JWT + single-use** en `auth-server/app/routes/ai_grant.py` — base para AI Gateway.
- **License validation** en `trading-client/app/services/license.py` — funciona, solo necesita el bug de `LocalUser` arreglado.
- **Plan limits** en `auth-server/app/services/rate_limit.py` — estructura extensible.
- **ExecutionEngine** — estructura correcta, solo necesita idempotencia y `Decimal` estricto.
- **RiskManager** — base válida para Risk Engine determinista futuro.
- **PriceStream WebSocket** — funciona bien, solo necesita abstracción para multi-broker.

### Refactorizar (Fase 1-2)

- `broker.py` ABC → reemplazar por `BrokerAdapter` con modelos de dominio normalizados.
- `binance_broker.py` → envolver en `BinanceAdapter` por composición.
- `factories.py` → reemplazar por `registry.py`.
- `helpers.py::resolve_binance_keys()` → `resolve_broker_credentials()` genérico.
- `routes/ai_agent.py::get_binance_balance()` → usar `adapter.get_account_balances()`.
- `routes/trading.py::list_positions()` → usar `adapter.get_ticker()` con `Decimal`.
- `routes/market.py::get_klines()` → usar adaptador para klines.
- `services/auth.py::get_current_user()` → poblar `binance_api_key_enc` desde `user_settings`.
- `services/crypto.py` → requerir `ENCRYPTION_KEY` explícita, eliminar fallback.

### Reemplazar (Fases 3-8)

- `ai/agent.py` → AIProvider (Local/Remote), agentes deterministas en `ai-server/`.
- Auto-close en `agent.py` → Risk Engine determinista con circuit breakers.
- `ExecutionEngine` sin idempotencia → Order Management con `idempotencyKey`.
- `float` en dinero → `Decimal` en todo el pipeline.
- `unsafe static mut PYTHON_CHILD` en Rust → manejo seguro del proceso hijo.

---

## 10. UI Legacy

- `trading-client/desktop/src/` — React 19, la UI activa.
- No se detectaron `dashboard.html` ni `landing.html` en `trading-client/`. Si existen en `app/` (monolito legacy), se documentan como legacy y no se tocan.
