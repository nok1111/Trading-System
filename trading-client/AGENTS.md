# Alvora Trading Platform — Project Info

## Architecture

Multi-broker crypto trading platform with AI co-pilot, desktop app (Tauri + React + TypeScript),
and Python backend (FastAPI).

### Repos
- `trading-client/` — FastAPI backend + Tauri desktop app
- `auth-server/` — Authentication server (FastAPI, JWT, 2FA TOTP)

## Build & Run

### Backend (trading-client)
```bash
cd trading-client
python -m uvicorn app.api.app:app --reload --port 8000
```

### Desktop (Tauri)
```bash
cd trading-client/desktop
npm install
npm run dev      # Vite dev server (port 1420)
npm run tauri dev  # Tauri + Vite
```

### Auth Server
```bash
cd auth-server
python -m uvicorn app.main:app --reload --port 8001
```

## Test commands

### Backend tests
```bash
cd trading-client
python -m pytest tests/ -v              # all tests (292)
python -m pytest tests/test_security.py -v
python -m pytest tests/test_monte_carlo.py -v
python -m pytest tests/test_attribution.py -v
python -m pytest tests/test_advanced_features.py -v
```

### Frontend typecheck
```bash
cd trading-client/desktop
npx tsc --noEmit                        # typecheck
npx vite build                          # production build
```

## Key directories

### Backend
- `app/api/app.py` — FastAPI app, middleware, route registration
- `app/api/routes/` — API route modules
- `app/services/` — business logic services
- `app/database/models/` — SQLAlchemy models
- `app/brokers/adapters/` — broker adapters (CCXT, OKX, Bybit, Binance)
- `app/brokers/registry.py` — broker registry
- `app/ai/` — AI providers (local, remote, copilot)
- `app/middleware/` — rate limiting, security headers
- `app/risk/` — risk engine, circuit breaker

### Frontend (desktop)
- `desktop/src/App.tsx` — main app, lazy-loaded pages
- `desktop/src/components/layout/Layout.tsx` — sidebar nav, tab system
- `desktop/src/components/` — UI components
- `desktop/src/lib/` — API clients, hooks, utils
- `desktop/src/pages/` — page components
- `desktop/src/i18n/translations/` — es.json, en.json

## API Endpoints (main groups)

| Prefix | Module | Description |
|--------|--------|-------------|
| `/api/auth` | auth-server | Login, register, 2FA, JWT |
| `/api/portfolio` | portfolio.py | Unified portfolio across brokers |
| `/api/brokers` | brokers.py, broker_data.py | Broker accounts, market data |
| `/api/trading` | trading.py | Orders, positions, backtests |
| `/api/copilot` | copilot.py | AI chat, suggestions, quick actions |
| `/api/intelligence` | intelligence.py | Market intel, backtest, optimize, Monte Carlo |
| `/api/social` | social.py | Leaders, signals, follow, auto-copy |
| `/api/dca` | dca_bots.py | DCA bot CRUD |
| `/api/audit` | audit.py | Audit logs, summary |
| `/api/attribution` | attribution.py | Performance attribution |
| `/api/health` | health.py | Health checks (live, ready, full) |
| `/api/cache` | cache.py | Cache monitoring |
| `/api/smart-alerts` | smart_alerts.py | AI-powered alerts |

## Brokers supported

- Binance (spot/futures) — native adapter
- OKX — CCXT adapter with OKX enhancements
- Bybit — CCXT adapter with Bybit enhancements
- Any CCXT-supported exchange via `ccxt_adapter.py`

## AI Providers

- **Groq** (default): `openai/gpt-oss-120b`
- **Gemini**: `gemini-flash-latest`
- **Ollama** (local): any local model
- **Remote**: custom HTTP endpoint

## Security features

- Rate limiting: sliding window per IP/user (auth 10/min, trading 30/min, default 100/min)
- Security headers: CSP, HSTS, X-Frame-Options, Permissions-Policy
- Audit logging: all sensitive actions logged to `SystemEvent` table
- 2FA: TOTP-based, enforced on auth server
- CORS: restricted to Tauri origins (localhost:1420, tauri.localhost)

## Strategies (backtest)

7 built-in strategies:
1. `trend_momentum` — EMA fast/slow crossover + RSI filter
2. `mean_reversion` — Bollinger Bands + RSI extremes
3. `breakout` — Donchian channel breakout
4. `grid` — grid trading in range
5. `macd_momentum` — MACD histogram momentum
6. `bollinger_squeeze` — volatility squeeze breakout
7. `supertrend` — Supertrend indicator follow
8. `rsi_divergence` — RSI divergence detection

Each supports custom parameters via `_run_*_custom` variants.

## Testing notes

- Tests use SQLite in-memory database
- No network calls in tests (all mocked)
- 292 backend tests, all passing
- Frontend: TypeScript strict mode, Vite build clean
