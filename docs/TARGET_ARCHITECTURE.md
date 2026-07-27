# Arquitectura Objetivo

> **Fecha**: 2025-01  
> **Propósito**: Describir la arquitectura meta del rework multi-broker con IA externa, aterrizada al proyecto real.  
> **Principio rector**: custodia 100% local de claves y ejecución; el servidor de IA nunca ve claves ni ejecuta órdenes.

---

## 1. Visión General

```
┌─────────────────────────────────────────────────────────┐
│                   CLIENTE LOCAL (Trading Client)         │
│                                                          │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Tauri   │  │  Broker      │  │  Market Data      │  │
│  │  UI      │  │  Adapters    │  │  (klines, WS,     │  │
│  │  (React) │  │  (Binance,   │  │   movers, ticks)  │  │
│  │          │  │   Bybit,     │  │                   │  │
│  │          │  │   Coinbase,  │  ├───────────────────┤  │
│  │          │  │   Kraken,    │  │  Risk Engine       │  │
│  │          │  │   OKX)       │  │  (determinista,    │  │
│  │          │  │              │  │   circuit breaker) │  │
│  │          │  ├──────────────┤  ├───────────────────┤  │
│  │          │  │  Order Mgmt  │  │  AI Gateway        │  │
│  │          │  │  (idempotency│  │  (Local/Remote     │  │
│  │          │  │   reconcile) │  │   Provider)        │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
│         │              │                │               │
│         └──────────────┴────────────────┘               │
│                        │                                 │
│              ┌─────────▼──────────┐                     │
│              │  FastAPI (18652)    │                     │
│              │  SQLite local       │                     │
│              │  Claves encriptadas │                     │
│              └─────────┬──────────┘                     │
└────────────────────────┼────────────────────────────────┘
                         │ HTTPS (JWT + HMAC servicio-a-servicio)
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   VPS (Cloud)                            │
│                                                          │
│  ┌──────────────┐    ┌───────────────────┐              │
│  │  Auth Server │    │  AI Server         │              │
│  │  (login,     │    │  (8 agentes,       │              │
│  │   licencia,  │    │   router de niveles│              │
│  │   grants,    │    │   JSON Schema,     │              │
│  │   pagos)     │    │   caché, tokens)   │              │
│  └──────────────┘    └───────────────────┘              │
│         PostgreSQL                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Servicios del Cliente Local

Todo lo que toca dinero, claves o ejecución vive en el cliente local. **Nada se envía al VPS que no sea JWT y metadatos anónimos.**

### 2.1 Broker Adapters

**Interfaz**: `BrokerAdapter` (ABC síncrono, `trading-client/app/brokers/base.py`)

- **Modelos normalizados** en `trading-client/app/brokers/models.py`: dataclasses inmutables con `Decimal` para todo importe monetario. Prohibido `float`.
- **Capacidades** en `trading-client/app/brokers/capabilities.py`: `BrokerCapabilities` declara qué soporta cada broker. `withdrawals` **siempre** `False` a nivel de tipo.
- **Registry** en `trading-client/app/brokers/registry.py`: `get_adapter(broker_id, credentials)` y `list_brokers()`. Único lugar con condicionales por broker.
- **Adaptadores**:
  - `BinanceAdapter` — envuelve `BinanceBroker` por composición (Fase 1).
  - `BybitAdapter`, `CoinbaseAdapter`, `KrakenAdapter`, `OKXAdapter` — stubs (Fase 7).

**Símbolos normalizados**: `BTC/USDT` (con slash) es el formato canónico. Cada adaptador traduce al formato del broker (`BTCUSDT` en Binance, `XBTUSDT` en Kraken, etc.).

**Estados de cuenta** (`BrokerAccountStatus`): 7 estados — `PENDING_VALIDATION`, `ACTIVE`, `SUSPENDED`, `API_KEY_INVALID`, `RATE_LIMITED`, `INSUFFICIENT_BALANCE`, `SECURITY_BLOCKED`.

### 2.2 Market Data

- Abstracción sobre `DataSource` existente + `PriceStream` WebSocket.
- Cada adaptador expone `get_market_info()`, `get_ticker()`, klines.
- `subscribe_market_data()` opcional para streaming en tiempo real.
- **Smart Money** (Binance leaderboard) se documenta como específico de Binance y queda fuera de la interfaz común — se accede directamente cuando el broker es Binance.

### 2.3 Risk Engine (Fase 5)

- **Determinista**: reglas explícitas, no LLM. Poder de veto sobre toda orden.
- **Circuit breakers**: 4 estados — `NORMAL`, `WARNING`, `HALT_TRADING`, `EMERGENCY_HALT`.
  - `WARNING`: reduce position size al 50%.
  - `HALT_TRADING`: bloquea nuevas compras, permite closes.
  - `EMERGENCY_HALT`: bloquea todo excepto cancelaciones.
- **Auditoría**: cada decisión de riesgo se persiste en `risk_events` con razón, severidad y contexto.
- **Reemplaza** el auto-close del agente IA: el trailing stop se mueve aquí con `Decimal`.

### 2.4 Order Management (Fase 6)

- **Órdenes internas**: el cliente crea una orden interna con `idempotencyKey` (UUID) antes de enviar al broker.
- **14 estados internos**: `DRAFT`, `VALIDATED`, `RISK_APPROVED`, `RISK_REJECTED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_REQUESTED`, `CANCELLED`, `REJECTED`, `EXPIRED`, `TIMEOUT`, `RECONCILING`, `RECONCILED`.
- **Reconciliación**: poll periódico del estado real en el broker vs estado interno.
- **Aprobación humana**: `LIVE_CONFIRMATION_REQUIRED` ya existe en config; se respeta.

### 2.5 AI Gateway (Fase 3)

- **`AIProvider`** interfaz con dos implementaciones:
  - `LocalAIProvider`: llama a Groq/Gemini/Ollama directamente (como hoy). Default.
  - `RemoteAIProvider`: llama al `ai-server` via HTTPS con JWT + HMAC servicio-a-servicio.
- **Feature flags**:
  - `USE_REMOTE_AI` (bool, default `False`): toggle entre local y remoto.
  - `REMOTE_AI_PERCENTAGE` (0-100): porcentaje de requests que van al remoto (shadow mode).
  - `ENABLE_AI_SHADOW_MODE` (bool): ejecuta ambos y compara, solo aplica el local.
- **Contrato versionado**: el `ai-server` expone `/v1/analyze` con un JSON Schema de entrada y salida. El cliente valida la salida antes de ejecutar.
- **Sin claves**: el `ai-server` nunca recibe API keys de broker ni datos sensibles del usuario. Solo recibe contexto de mercado anónimo (precios, movers, posiciones agregadas sin símbolos si se configura).

---

## 3. Servicios del VPS

### 3.1 Auth Server (existente, extendido)

- Mantiene: login, JWT, suscripciones, licencia, grants de IA, pagos (Binance Pay).
- **Nuevo**: endpoint para validar HMAC servicio-a-servicio del `ai-server`.
- **No cambia**: no almacena ni procesa claves de broker ni datos de trading.

### 3.2 AI Server (nuevo, Fase 4)

- **Servicio independiente** (`ai-server/`), no dentro de `auth-server/`.
- **Router de niveles**: 3 niveles de modelo según plan:
  - **Económico** (free): modelo pequeño/fast (ej: `llama-3.1-8b`).
  - **Medio** (pro): modelo mediano (ej: `llama-3.3-70b`).
  - **Avanzado** (premium): modelo grande o ensemble (ej: GPT-4o + Claude).
- **8 agentes especializados**:
  1. Market Analyst — analiza mercado general.
  2. Risk Analyst — evalúa riesgo de portfolio.
  3. Strategy Selector — elige estrategia por condición.
  4. Entry Strategist — identifica puntos de entrada.
  5. Exit Strategist — identifica puntos de salida.
  6. Portfolio Manager — balance y diversificación.
  7. Sentiment Analyst — noticias y sentimiento.
  8. Performance Monitor — métricas y ajustes.
- **Seguridad**:
  - HMAC servicio-a-servicio + nonce + timestamp window (5 min).
  - JWT del usuario validado contra auth-server.
  - Rate limiting por usuario y por IP.
- **Validación de salida**: cada respuesta del LLM se valida contra JSON Schema antes de devolver al cliente. Si no valida, se rechaza.
- **Caché compartida**: `analysis:{broker}:{market}:{symbol}:{timeframe}:{dataVersion}` — evita recomputar análisis si los datos no cambiaron.
- **Contabilidad de tokens**: registra tokens consumidos por usuario para facturación y cuota.

---

## 4. Capacidades por Broker

| Capacidad | Binance | Bybit | Coinbase | Kraken | OKX |
|---|---|---|---|---|---|
| Spot | ✅ | ✅ | ✅ | ✅ | ✅ |
| Margin | ❌ | ✅ | ❌ | ✅ | ✅ |
| Futures | ❌ | ✅ | ✅ | ❌ | ✅ |
| Staking | ❌ | ❌ | ✅ | ✅ | ✅ |
| Earn | ✅ | ❌ | ✅ | ❌ | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ |
| Market orders | ✅ | ✅ | ✅ | ✅ | ✅ |
| Limit orders | ✅ | ✅ | ✅ | ✅ | ✅ |
| Stop orders | ✅ | ✅ | ❌ | ✅ | ✅ |
| **Withdrawals** | **❌** | **❌** | **❌** | **❌** | **❌** |

> `withdrawals` es **siempre `False`** por diseño. No se implementa ni se planea implementar.

---

## 5. Niveles de Modelo

| Plan | Nivel | Modelo (ejemplo) | Cuota diaria | Intervalo mín. |
|---|---|---|---|---|
| Free | Económico | `llama-3.1-8b-instant` | 50 | 120s |
| Pro | Medio | `llama-3.3-70b-versatile` | 500 | 15s |
| Premium | Avanzado | GPT-4o + ensemble | 99999 | 10s |

El router del `ai-server` selecciona el modelo según el plan del usuario (validado via JWT). El cliente no elige el modelo directamente cuando usa `RemoteAIProvider`.

---

## 6. Contrato App ↔ IA (Versionado)

### Request (`POST /v1/analyze`)

```json
{
  "version": "1",
  "user_id_hash": "sha256(jwt_sub + salt)",
  "plan": "pro",
  "context": {
    "acc": {"cash": "5000.00", "equity": "5200.00", "positions": 3},
    "positions": [{"symbol": "BTC/USDT", "qty": "0.1", "entry": "45000", "pnl": "+2.1%"}],
    "market": {"spot_up": [...], "spot_dn": [...], "futures_up": [...]}
  }
}
```

### Response (validado con JSON Schema)

```json
{
  "version": "1",
  "analysis_id": "uuid",
  "market_overview": "...",
  "actions": [
    {
      "type": "buy",
      "symbol": "BTC/USDT",
      "confidence": 0.8,
      "stop_loss_pct": 3.0,
      "take_profit_pct": 8.0,
      "reason": "..."
    }
  ],
  "risk_assessment": "...",
  "tokens_used": 450
}
```

### Seguridad del contrato

- **Sin claves** en el request. Nunca.
- **Sin símbolos sensibles** si el usuario lo configura (modo privacy).
- **HMAC** del payload completo con clave compartida rotada.
- **Timestamp** con ventana de 5 min.
- **Nonce** único por request (anti-replay).

---

## 7. Feature Flags

| Flag | Default | Descripción |
|---|---|---|
| `ENABLE_MULTI_BROKER` | `False` | Habilita selección de broker en UI. Solo Binance cuando `False`. |
| `USE_REMOTE_AI` | `False` | Usa `RemoteAIProvider` en lugar de `LocalAIProvider`. |
| `REMOTE_AI_PERCENTAGE` | `0` | % de requests que van al remoto (0-100). |
| `ENABLE_AI_SHADOW_MODE` | `False` | Ejecuta local y remoto en paralelo, solo aplica local. |
| `ENABLE_AUTOMATIC_EXECUTION` | `True` | Permite ejecución automática de órdenes del agente. |
| `ENABLE_ADVANCED_MODEL` | `False` | Permite usar modelo avanzado (premium) en modo remoto. |

---

## 8. Principios de Diseño

1. **Custodia local**: claves API, ejecución de órdenes y dinero real nunca salen del cliente.
2. **Defensa en profundidad**: Risk Engine con veto, circuit breakers, idempotencia, aprobación humana.
3. **Decimal estricto**: prohibido `float` para dinero o cantidades en código nuevo.
4. **Sin `if broker ==`**: toda lógica por broker vive en el adaptador o en el registry.
5. **Contratos versionados**: la comunicación app↔IA usa JSON Schema y versionado explícito.
6. **Observabilidad**: cada decisión (riesgo, orden, análisis IA) se persiste con contexto completo.
7. **Reversibilidad**: feature flags permiten volver al comportamiento anterior sin deploy.
8. **No retiros**: `withdrawals` siempre `False`. No se implementa ni se planea.
