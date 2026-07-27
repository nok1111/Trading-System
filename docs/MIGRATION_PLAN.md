# Plan de Migración

> **Fecha**: 2025-01  
> **Propósito**: Definir las fases para migrar del estado actual a la arquitectura objetivo sin romper funcionalidad existente.  
> **Principio**: cada fase es incremental, reversible mediante feature flags, y verificable con tests.

---

## Resumen de Fases

| Fase | Nombre | Entrega | Riesgo |
|---|---|---|---|
| 0 | Documentación | 4 docs + marcar obsoletos | Ninguno (solo docs) |
| 1 | BrokerAdapter | Interfaz + BinanceAdapter + tests | Bajo (aditivo + migración read-only) |
| 2 | Modelos normalizados | Market Data y Portfolio en Decimal | Bajo-Medio |
| 3 | AIProvider | Local/Remote provider + feature flags | Medio |
| 4 | AI Server | `ai-server/` con 8 agentes + HMAC | Medio-Alto |
| 5 | Risk Engine | Determinista + circuit breakers + retira auto-close | Alto |
| 6 | Order Management | Idempotencia + 14 estados + reconciliación | Alto |
| 7 | Multi-broker real | Bybit/Coinbase/Kraken/OKX adaptadores | Medio |
| 8 | Producción gradual | Shadow mode → usuarios internos → grupo pequeño | Alto |

---

## Fase 0 — Documentación (sin cambios de código)

### Entradas
- Inspección completa del repo (ver `CURRENT_ARCHITECTURE_AUDIT.md`).

### Salidas
- `docs/CURRENT_ARCHITECTURE_AUDIT.md`
- `docs/TARGET_ARCHITECTURE.md`
- `docs/MIGRATION_PLAN.md` (este documento)
- `docs/SECURITY_REVIEW.md`
- `docs/architecture.md` y `docs/install.md` marcados como obsoletos.
- Nota en `README.md` aclarando que describe el monolito legacy.

### Criterios de aceptación
- Los 4 documentos existen con rutas y líneas reales.
- No se modifica código de aplicación.

---

## Fase 1 — BrokerAdapter (comportamiento idéntico)

### 1a. Núcleo aditivo (riesgo cero)

**Entradas**: `broker.py`, `binance_broker.py`, `mock_broker.py`, `factories.py`.

**Salidas (ficheros nuevos)**:

| Fichero | Contenido |
|---|---|
| `trading-client/app/brokers/models.py` | Dataclasses inmutables con `Decimal`: `BrokerInfo`, `BrokerCredentials`, `CredentialValidationResult`, `Balance`, `PortfolioSnapshot`, `Position`, `BrokerOrder`, `OrderRequest`, `ValidatedOrderRequest`, `OrderExecutionResult`, `CancelOrderRequest`, `OrderCancellationResult`, `MarketInfo`, `Ticker`, `Candle`, `Fee`. Enums: `MarketType`, `OrderSide`, `OrderType`, `OrderStatus`, `BrokerAccountStatus` (7 estados). |
| `trading-client/app/brokers/capabilities.py` | `BrokerCapabilities` con `withdrawals` forzado a `False`. |
| `trading-client/app/brokers/base.py` | ABC `BrokerAdapter` síncrono + excepciones tipadas. |
| `trading-client/app/brokers/adapters/binance_adapter.py` | `BinanceAdapter` por composición de `BinanceBroker`. |
| `trading-client/app/brokers/adapters/{bybit,coinbase,kraken,okx}_adapter.py` | Stubs con `NotImplementedError`. |
| `trading-client/app/brokers/registry.py` | `get_adapter()`, `list_brokers()`. Detrás de `ENABLE_MULTI_BROKER`. |

**No se modifica**: `broker.py`, `binance_broker.py`, `mock_broker.py`, `factories.py`, `ExecutionEngine`.

### 1b. Migración de call-sites de solo lectura

**Entradas**: rutas que hacen llamadas crudas a Binance.

**Salidas**:

| Fichero | Cambio |
|---|---|
| `api/helpers.py` | `resolve_binance_keys()` → `resolve_broker_credentials()` genérico. Alias mantiene nombre antiguo. Corrige bug de `LocalUser` para claves de broker. |
| `api/routes/ai_agent.py` | `get_binance_balance()` → `adapter.get_account_balances()` + `get_portfolio()`. MXN conversion se mantiene. |
| `api/routes/trading.py` | `list_positions()` → refresco de precio vía `adapter.get_ticker()` con `Decimal`. |
| `api/routes/market.py` | `get_klines()` → adaptador. Smart-money queda como específico de Binance. |

**Fuera de 1b**: `ai/agent.py` (intacto), `data/price_stream.py`, `data/binance_leaderboard.py`, `paper_trading/`, `ml/`, rutas de escritura de órdenes.

**Invariante**: las respuestas JSON que consume el frontend deben ser byte-a-byte idénticas.

### 1c. Tests

**Salidas**:

| Fichero | Contenido |
|---|---|
| `trading-client/pyproject.toml` | pytest con `pythonpath=["."]`, ruff con misma config que la raíz. |
| `trading-client/tests/test_broker_models.py` | Todo importe es `Decimal`; normalización de símbolos. |
| `trading-client/tests/test_binance_adapter.py` | Firma HMAC, stepSize, MIN_NOTIONAL, mapeo de estados, mapeo de errores, 429, timeout. |
| `trading-client/tests/test_broker_registry.py` | Resolución de adaptadores, stubs lanzan `NotImplementedError`, `withdrawals` siempre `False`. |
| `trading-client/tests/test_api_parity.py` | Snapshot de respuestas de `/api/binance/balance` y `/api/positions`. |

**Sin red**: monkeypatch de `httpx.get`/`httpx.post`/`httpx.delete`.

### Criterios de aceptación
- `trading-client/tests` pasa.
- Suite legacy (`tests/` en raíz) sigue pasando sin modificaciones.
- App Tauri arranca y las respuestas de API son idénticas.
- No se habilitan retiros. No se toca la ruta de escritura de órdenes.

---

## Fase 2 — Modelos Normalizados en Market Data / Portfolio

### Entradas
- `BinanceAdapter` funcionando, modelos normalizados en `brokers/models.py`.
- `data/binance_source.py`, `data/price_stream.py`, `routes/market.py`.

### Salidas
- `MarketDataSource` abstraído detrás del adaptador: klines, movers, ticker.
- `PortfolioSnapshot` y `Position` (modelo de dominio) consumidos por rutas y ExecutionEngine.
- Trailing stop movido a `Decimal` (pero sigue en `agent.py` por ahora).
- `float` eliminado de `routes/market.py::get_klines()` y `routes/trading.py::list_positions()`.

### Feature flags
- `ENABLE_MULTI_BROKER` controla si se usa el adaptador o el código legacy.

### Mapeo de tablas
- No hay migración de BD en esta fase. Los modelos ORM (`Order`, `Position`, `AccountSnapshot`) se conservan. Los modelos de dominio (`brokers/models.py`) son paralelos y se traducen en la capa de API.

---

## Fase 3 — AIProvider (Local / Remote)

### Entradas
- `ai/agent.py` intacto.
- `services/license.py` con grant system funcionando.

### Salidas
- `trading-client/app/ai/provider.py`: interfaz `AIProvider`.
- `trading-client/app/ai/local_provider.py`: `LocalAIProvider` — extrae la lógica actual de `_ask_groq`/`_ask_gemini`/`_ask_ollama`/`_ask_openai_compat`.
- `trading-client/app/ai/remote_provider.py`: `RemoteAIProvider` — llama al `ai-server` via HTTPS.
- `agent.py` refactorizado para usar `AIProvider` (pero la lógica de buy-only y auto-close se preserva).
- Feature flags: `USE_REMOTE_AI`, `REMOTE_AI_PERCENTAGE`, `ENABLE_AI_SHADOW_MODE`.

### Invariante
- Con `USE_REMOTE_AI=False` (default), el comportamiento es idéntico al actual.

---

## Fase 4 — AI Server

### Entradas
- `AIProvider` interfaz definida.
- Auth server con grant system.

### Salidas
- `ai-server/`: nuevo servicio FastAPI independiente.
  - Router de niveles (económico/medio/avanzado) según plan del usuario.
  - 8 agentes especializados.
  - Validación de salida con JSON Schema.
  - Caché compartida `analysis:{broker}:{market}:{symbol}:{timeframe}:{dataVersion}`.
  - Contabilidad de tokens.
  - HMAC servicio-a-servicio + nonce + timestamp.
- Auth server extendido con endpoint para validar HMAC del ai-server.

### Seguridad
- El ai-server nunca recibe claves de broker ni datos sensibles.
- Comunicación via HTTPS únicamente.
- JWT del usuario validado contra auth-server.

---

## Fase 5 — Risk Engine Determinista

### Entradas
- `risk/risk_manager.py` existente como base.
- Auto-close en `ai/agent.py` como referencia.

### Salidas
- `trading-client/app/risk/engine.py`: Risk Engine determinista con:
  - Reglas explícitas (max position size, max open positions, daily loss limit, diversificación).
  - Circuit breakers: `NORMAL` → `WARNING` → `HALT_TRADING` → `EMERGENCY_HALT`.
  - Poder de veto sobre toda orden.
  - Auditoría en `risk_events`.
- Trailing stop movido de `agent.py` al Risk Engine con `Decimal`.
- Auto-close thread eliminado de `agent.py`.
- `ENABLE_AUTOMATIC_EXECUTION` flag para bloquear toda ejecución automática.

### Invariante
- Con `ENABLE_AUTOMATIC_EXECUTION=True` y `USE_REMOTE_AI=False`, el comportamiento es equivalente (compras automáticas + trailing stop), pero ahora vía Risk Engine.

---

## Fase 6 — Order Management

### Entradas
- `ExecutionEngine` existente como base.
- `Order` model en BD.

### Salidas
- `trading-client/app/execution/order_manager.py`: Order Management con:
  - `idempotencyKey` (UUID) por orden.
  - 14 estados internos: `DRAFT` → `VALIDATED` → `RISK_APPROVED` → `SUBMITTED` → `PARTIALLY_FILLED` → `FILLED` (o ramas de cancelación/rechazo/expiración).
  - Reconciliación periódica: poll del estado real en el broker vs estado interno.
  - Aprobación humana cuando `LIVE_CONFIRMATION_REQUIRED=True`.
- `ExecutionEngine` refactorizado para delegar en `OrderManager`.

### Mapeo de tablas
- `orders` table: añadir columna `idempotency_key` (String, unique, indexed).
- `orders` table: añadir columna `internal_status` (String, default `DRAFT`).
- `positions` table: sin cambios.
- Migración Alembic para añadir columnas.

---

## Fase 7 — Multi-Broker Real

### Entradas
- `BrokerAdapter` interfaz + registry.
- Stubs de Bybit/Coinbase/Kraken/OKX.

### Salidas
- Implementación real de adaptadores (orden: Bybit → Coinbase → Kraken → OKX).
- UI: selector de broker en Settings.
- Primero read-only (saldos, posiciones, precios), luego paper trading, luego live aprobado.
- `ENABLE_MULTI_BROKER=True` habilita el selector.

### Mapeo de tablas
- `user_settings`: añadir `broker_id` (String, default `"binance"`).
- `user_settings`: renombrar o generalizar `binance_api_key_enc` → `broker_api_key_enc`, `binance_api_secret_enc` → `broker_api_secret_enc`.
- Migración Alembic con backfill (`broker_id="binance"` para filas existentes).

---

## Fase 8 — Producción Gradual

### Entradas
- Todos los componentes funcionando con feature flags.

### Salidas
- Shadow mode: `ENABLE_AI_SHADOW_MODE=True` — ejecuta local y remoto en paralelo, compara resultados, solo aplica local.
- Usuarios internos: `USE_REMOTE_AI=True` para un grupo seleccionado.
- Grupo pequeño: rollout gradual con métricas (latencia, tasa de acierto, tokens consumidos).
- Rollback: revertir feature flags a `False` sin deploy.

### Métricas a monitorear
- Tasa de acierto del agente (local vs remoto).
- Latencia de respuesta del ai-server.
- Tokens consumidos por usuario.
- Tasa de rechazos del Risk Engine.
- Tasa de errores de reconciliación.

---

## Mapeo de Tablas: Resumen

| Tabla | Fase | Cambio |
|---|---|---|
| `orders` | 6 | + `idempotency_key` (String, unique, indexed) |
| `orders` | 6 | + `internal_status` (String, default `DRAFT`) |
| `user_settings` | 7 | + `broker_id` (String, default `"binance"`) |
| `user_settings` | 7 | Generalizar `binance_api_key_enc` → `broker_api_key_enc` |
| `positions` | — | Sin cambios |
| `signals` | — | Sin cambios |
| `trades` | — | Sin cambios |
| `account_snapshots` | — | Sin cambios |
| `risk_events` | 5 | + `circuit_breaker_state` (String, nullable) |
| `system_events` | — | Sin cambios |
| *Nuevas* | 4 | `ai_analysis_cache` (en ai-server, no en trading-client) |
| *Nuevas* | 6 | `order_reconciliations` (id, order_id, broker_status, internal_status, timestamp, diff) |

---

## Feature Flags: Resumen

| Flag | Fase | Default | Descripción |
|---|---|---|---|
| `ENABLE_MULTI_BROKER` | 1 | `False` | Habilita multi-broker en registry y UI. |
| `USE_REMOTE_AI` | 3 | `False` | Usa RemoteAIProvider. |
| `REMOTE_AI_PERCENTAGE` | 3 | `0` | % de requests al remoto (shadow). |
| `ENABLE_AI_SHADOW_MODE` | 3 | `False` | Ejecuta local y remoto en paralelo. |
| `ENABLE_AUTOMATIC_EXECUTION` | 5 | `True` | Permite ejecución automática. |
| `ENABLE_ADVANCED_MODEL` | 4 | `False` | Permite modelo avanzado (premium). |

---

## Gestión de Riesgos por Fase

| Riesgo | Mitigación |
|---|---|
| Deriva de respuestas de API en 1b | Tests de paridad (`test_api_parity.py`). |
| Confusión de paquetes `app/` vs `trading-client/app/` | `pythonpath=["."]` en `pyproject.toml`; pytest desde `trading-client/`. |
| Auto-close deja de funcionar al mover a Risk Engine | Shadow mode: ambos corren en paralelo hasta confirmar paridad. |
| AI server no disponible | Fallback automático a `LocalAIProvider`. |
| Pérdida de datos en migración de BD | Migraciones Alembic con backfill y rollback. |
| Secretos expuestos durante la migración | Rotación documentada en `SECURITY_REVIEW.md`; parches aplicados por fase. |
