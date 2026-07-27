# Plan de Migración — Plataforma de Inteligencia de Mercado Autónoma

> **Fecha**: 2025-07
> **Propósito**: Migrar el ai-server de arquitectura request-response (chatbot) a plataforma de inteligencia autónoma 24/7 con análisis compartido, event-driven execution, y personalización por usuario.
> **Principio**: análisis global una vez, personalización por usuario sin IA. Ahorro de tokens del 80-90%.

---

## Resumen de Fases

| Fase | Nombre | Entrega | Riesgo |
|---|---|---|---|
| A | Market Data Engine | Indicadores deterministas + feeds | Bajo (aditivo) |
| B | Agentes IA (8 + Consensus) | Nuevos prompts, schemas, event triggers | Medio-Alto |
| C | Market Knowledge Base | Storage de señales, alertas, escenarios | Medio |
| D | Portfolio Matcher + Notifications | Personalización determinista + pending queue | Medio |
| E | Event-Driven Scheduler | Triggers, intervalos, graceful degradation | Alto |
| F | API + Integración | Nuevos endpoints, migrar trading-client | Medio |

---

## Arquitectura Objetivo

```
DATA LAYER
├── Exchange feeds (precios, velas, volumen, order book, funding, OI)
├── News feeds
├── On-chain feeds
├── Macro feeds
└── Sentiment feeds
         │
         ▼
DETERMINISTIC PROCESSING (Market Data Engine — no IA)
├── Indicators (RSI, MACD, EMA, ATR, volatilidad, volumen relativo)
├── Correlations
├── Liquidity analysis
├── Anomaly detection
└── Data validation
         │
         ▼
AI AGENTS (event-driven, no en cada ciclo)
├── Technical Market Analyst
├── News Analyst
├── Sentiment Analyst
├── On-chain Analyst
├── Macro Analyst
├── Crash Risk Detector
├── Opportunity Detector
└── Contrarian Agent
         │
         ▼
CONSENSUS ENGINE (Consensus Agent)
         │
         ▼
MARKET KNOWLEDGE BASE (tablas: signals, alerts, reports, scenarios, invalidations)
         │
         ▼
USER PERSONALIZATION (determinista, no IA)
├── Portfolio Matcher
├── Risk Profile Matcher
├── Notification Generator
└── Pending Information Queue (PENDING/DELIVERED/READ/EXPIRED/SUPERSEDED/CANCELLED)
```

---

## Fase A — Market Data Engine (determinista, no IA)

### Entradas
- `trading-client/app/data/` existente (BinanceSource, MarketDataService, price_stream)
- `trading-client/app/strategies/` indicadores existentes

### Salidas
- `ai-server/app/services/market_data.py`: MarketDataEngine con:
  - `compute_indicators(symbol) → dict` (RSI, MACD, EMA, ATR, volatilidad, volumen relativo)
  - `compute_liquidity(symbol) → dict` (spread, depth, order book changes)
  - `compute_correlations(symbols) → dict`
  - `detect_anomalies(symbol) → list[dict]`
  - `validate_data(symbol) → DataQuality`
  - Cache de resultados con TTL por tipo de indicador
- `ai-server/app/services/feeds/`:
  - `news_feed.py`: interface + stubs (RSS/API news)
  - `onchain_feed.py`: interface + stubs (Glassnode/CryptoQuant API)
  - `macro_feed.py`: interface + stubs (FRED/yahoo finance)
  - `sentiment_feed.py`: interface + stubs (social media APIs)
- Config en `ai-server/app/config.py`:
  - `MARKET_DATA_REFRESH_SECONDS: int = 300`
  - `INDICATOR_TIMEFRAMES: str = "15m,1h,4h,1d"`
  - `ENABLE_NEWS_FEED: bool = False`
  - `ENABLE_ONCHAIN_FEED: bool = False`
  - `ENABLE_MACRO_FEED: bool = False`
  - `ENABLE_SENTIMENT_FEED: bool = False`

### Invariante
- MarketDataEngine no llama IA. Solo computa y cachea.
- Feeds tienen stubs que retornan datos vacíos — se implementan en Fase 7 (Multi-Broker Real).

---

## Fase B — Agentes IA (8 + Consensus)

### Entradas
- `ai-server/app/services/agents.py` actual (10 agentes)
- Documento de arquitectura del usuario

### Salidas
- `ai-server/app/services/agents.py` reescrito con 9 agentes IA:

| # | Agente | Usa IA | Intervalo | Trigger |
|---|---|---|---|---|
| 1 | Technical Market Analyst | Sí | 15-30 min | Cambio en indicadores |
| 2 | News Analyst | Sí | On news | Nueva noticia |
| 3 | Sentiment Analyst | Sí | 15-30 min | Cambio de sentimiento |
| 4 | On-chain Analyst | Sí | 30-60 min | Movimiento de ballena |
| 5 | Macro Analyst | Sí | 1h o evento | Evento macro |
| 6 | Crash Risk Detector | Sí + reglas | 3-5 min | Anomalía detectada |
| 7 | Opportunity Detector | Sí | 10-15 min | Cambio técnico |
| 8 | Contrarian Agent | Sí | Tras signal | Signal generada |
| 9 | Consensus Agent | Sí | Cuando cambien datos | Inputs de otros agentes |

### Agentes eliminados del stack IA (ya son deterministas):
- ~~Orchestrator~~ → reemplazado por Consensus Agent + Event Scheduler
- ~~User Profile Manager~~ → reemplazado por Portfolio Matcher (determinista)
- ~~Risk Manager~~ → ya es RiskEngine en trading-client (Fase 5)
- ~~Portfolio Manager~~ → reemplazado por Portfolio Matcher (determinista)
- ~~Execution Manager~~ → ya es OrderManager en trading-client (Fase 6)
- ~~Advisor/Explainer~~ → reemplazado por Notification Generator (determinista)
- ~~Auditor/Guardian~~ → reemplazado por Contrarian Agent + validación determinista

### Schemas JSON por agente:
- Technical: `{asset, timeframes, trendStrength, volatility, supportZones, resistanceZones, technicalBias, confidence}`
- News: `{headline, affectedAssets, impact, severity, timeHorizon, confidence, isRumor, pricedIn}`
- Sentiment: `{asset, sentimentScore, narrative, euphoria, fear, coordinated, riskFlags}`
- On-chain: `{asset, exchangeFlows, whaleMovements, reserves, stablecoins, onchainBias, confidence}`
- Macro: `{macroRegime, cryptoImpact, equityImpact, usdImpact, durationEstimate, keyEvents}`
- Crash: `{asset, crashRisk, riskLevel, horizon, reasons}`
- Opportunity: `{asset, suggestion, entryZone, invalidatedBelow, targets, timeHorizon, confidence}`
- Contrarian: `{targetSignal, counterArguments, divergence, manipulationRisk, recommendation}`
- Consensus: `{asset, decision, confidence, agreement, mainReasons, mainRisks, scenarios}`

### `ai-server/app/services/consensus.py`:
- `run_consensus(agent_results: dict) → ConsensusResult`
- Recibe resultados de todos los agentes
- Llama al LLM con el prompt del Consensus Agent
- Valida contra schema
- Genera escenarios probabilísticos (bullish/base/bearish con rangos)

### Invariante
- Los agentes no conocen al usuario.
- El Contrarian Agent siempre se ejecuta después de Opportunity Detector.
- El Consensus Agent no se ejecuta si no hay suficientes inputs.

---

## Fase C — Market Knowledge Base

### Entradas
- Modelo de datos nuevo

### Salidas
- `ai-server/app/database/` (nuevo — ai-server no tenía BD):
  - `base.py`: SQLAlchemy Base + engine (SQLite o PostgreSQL)
  - `session.py`: SessionLocal + get_db
  - `models/`:
    - `market_signal.py`: MarketSignal (id, asset, signal_type, decision, confidence, reasons, risks, timestamp, expires_at, status, consensus_data JSON)
    - `market_alert.py`: MarketAlert (id, asset, alert_type, severity, message, timestamp, expires_at, status)
    - `market_scenario.py`: MarketScenario (id, asset, horizon, current_price, scenarios JSON, timestamp, expires_at)
    - `market_report.py`: MarketReport (id, asset, report_type, content, timestamp, period)
    - `signal_invalidation.py`: SignalInvalidation (id, signal_id, reason, timestamp)
    - `pending_notification.py`: PendingNotification (id, user_id_hash, notification_type, content JSON, status, created_at, delivered_at, read_at, expires_at, supersedes_id)
  - `__init__.py`: exports

### Notification states:
- `PENDING`: creada, esperando entrega
- `DELIVERED`: enviada al usuario
- `READ`: leída por el usuario
- `EXPIRED`: caducó sin leer
- `SUPERSEDED`: reemplazada por una más reciente
- `CANCELLED`: cancelada manualmente

### Invariante
- Las señales tienen `expires_at` — no se entregan señales vencidas.
- `SUPERSEDED` invalida automáticamente la notificación anterior.

---

## Fase D — Portfolio Matcher + Notifications

### Entradas
- Market Knowledge Base (señales, alertas, escenarios)
- User portfolio (enviado por trading-client en el request)

### Salidas
- `ai-server/app/services/portfolio_matcher.py`:
  - `match_signals_to_user(signals: list, user_portfolio: dict, risk_profile: dict) → list[PersonalRecommendation]`
  - No usa IA — puro cruce determinista
  - Una misma señal global produce recomendaciones diferentes según:
    - Monedas que posee el usuario
    - Precio promedio de compra
    - Exposición actual
    - Perfil de riesgo
    - Broker
- `ai-server/app/services/notification_generator.py`:
  - `generate_notifications(recommendations: list) → list[PendingNotification]`
  - Traduce decisiones técnicas a lenguaje claro (templates, no IA)
  - Agrupa notificaciones por relevancia
  - Marca `SUPERSEDED` en notificaciones anteriores del mismo asset/tipo
- `ai-server/app/services/pending_queue.py`:
  - `get_pending(user_id_hash) → list[PendingNotification]`
  - `mark_delivered(notification_id)`
  - `mark_read(notification_id)`
  - `expire_stale()`
  - `supersede_old(new_notification)` — marca como SUPERSEDED las notificaciones anteriores del mismo tipo/asset

### Invariante
- Portfolio Matcher no llama IA.
- Notification Generator no llama IA (usa templates).
- Solo se generan notificaciones para eventos relevantes (no cada ciclo).

---

## Fase E — Event-Driven Scheduler

### Entradas
- Fases A-D completas

### Salidas
- `ai-server/app/services/scheduler.py`:
  - `EventScheduler` con loop principal:
    1. Market Data Engine corre en intervalos configurables
    2. Detecta eventos (cambio material, anomalía, noticia nueva)
    3. Dispara agentes relevantes según el evento
    4. Consensus Agent corre cuando hay nuevos inputs
    5. Guarda resultados en Market Knowledge Base
    6. Portfolio Matcher + Notification Generator generan notificaciones pendientes
  - Event triggers:
    - `SUPPORT_BREAK` → Technical + Crash + Consensus
    - `NEWS_CRITICAL` → News + Macro + Consensus
    - `WHALE_MOVEMENT` → On-chain + Crash + Consensus
    - `SENTIMENT_SHIFT` → Sentiment + Consensus
    - `OPPORTUNITY_DETECTED` → Opportunity + Contrarian + Consensus
    - `NO_CHANGE` → No llamar IA
  - Intervalos configurables por agente
  - Graceful degradation: si un agente falla, Consensus corre con los disponibles
  - Timeout por agente (no bloquea el pipeline)

### Config en `ai-server/app/config.py`:
```python
SCHEDULER_ENABLED: bool = False  # feature flag
SCHEDULER_INTERVAL_SECONDS: int = 60
AGENT_TIMEOUT_SECONDS: int = 30
CONSENSUS_MIN_AGENTS: int = 3  # mínimo de agentes para correr consensus
```

### Invariante
- Con `SCHEDULER_ENABLED=False`, el sistema funciona como antes (request-response).
- Con `SCHEDULER_ENABLED=True`, el scheduler corre 24/7 en background.

---

## Fase F — API + Integración

### Entradas
- Fases A-E completas

### Salidas
- `ai-server/app/routes/`:
  - `analyze.py`: mantener `/v1/analyze` legacy (backward compat)
  - `intelligence.py`: nuevos endpoints:
    - `GET /v1/intelligence/signals` — señales globales recientes
    - `GET /v1/intelligence/alerts` — alertas activas
    - `GET /v1/intelligence/scenarios/{asset}` — escenarios probabilísticos
    - `GET /v1/intelligence/reports/{asset}` — reportes detallados
    - `GET /v1/intelligence/pending` — notificaciones pendientes del usuario
    - `POST /v1/intelligence/pending/{id}/read` — marcar como leída
    - `GET /v1/intelligence/portfolio-match` — personalización por usuario
  - `scheduler.py`:
    - `POST /v1/scheduler/start` — iniciar scheduler
    - `POST /v1/scheduler/stop` — detener scheduler
    - `GET /v1/scheduler/status` — estado del scheduler
- `trading-client/app/ai/agent.py`:
  - Cuando `USE_REMOTE_AI=True`, consultar `/v1/intelligence/pending` en lugar de `/v1/analyze`
  - Integrar señales del ai-server con RiskEngine + OrderManager locales

### Invariante
- `/v1/analyze` sigue funcionando para backward compatibility.
- Los nuevos endpoints requieren JWT + HMAC.
- El trading-client puede usar ambos modos (legacy vs nuevo) vía feature flags.

---

## Feature Flags: Resumen

| Flag | Fase | Default | Descripción |
|---|---|---|---|
| `SCHEDULER_ENABLED` | E | `False` | Habilita el scheduler 24/7 |
| `ENABLE_NEWS_FEED` | A | `False` | Habilita feed de noticias |
| `ENABLE_ONCHAIN_FEED` | A | `False` | Habilita feed on-chain |
| `ENABLE_MACRO_FEED` | A | `False` | Habilita feed macro |
| `ENABLE_SENTIMENT_FEED` | A | `False` | Habilita feed de sentimiento |
| `USE_INTELLIGENCE_API` | F | `False` | Trading-client usa nuevos endpoints |
| `CONSENSUS_MIN_AGENTS` | E | `3` | Mínimo de agentes para consensus |

---

## Mapeo de Tablas: Resumen

| Tabla | Fase | Descripción |
|---|---|---|
| `market_signals` | C | Señales globales con consenso |
| `market_alerts` | C | Alertas de riesgo |
| `market_scenarios` | C | Escenarios probabilísticos |
| `market_reports` | C | Reportes periódicos |
| `signal_invalidations` | C | Invalidaciones de señales |
| `pending_notifications` | C | Notificaciones pendientes por usuario |

---

## Gestión de Riesgos por Fase

| Riesgo | Mitigación |
|---|---|
| Agentes lentos bloquean pipeline | Timeout + graceful degradation |
| Señales desactualizadas | `expires_at` + invalidación automática |
| Costo de tokens alto | Event-driven, no ejecutar si no hay cambios |
| Feeds no disponibles | Stubs retornan vacío, agentes marcan INSUFFICIENT_DATA |
| Migración rompe trading-client | Feature flags + backward compat en /v1/analyze |
| BD nueva en ai-server | SQLite para dev, PostgreSQL para prod |

---

## Orden de Implementación

1. **Fase A** — Market Data Engine (sin IA, puro cálculo)
2. **Fase C** — Market Knowledge Base (tablas, sin lógica)
3. **Fase B** — Agentes IA + Consensus (prompts, schemas, consensus engine)
4. **Fase D** — Portfolio Matcher + Notifications (determinista)
5. **Fase E** — Event-Driven Scheduler (orquesta todo)
6. **Fase F** — API + Integración (endpoints + trading-client)
