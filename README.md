# Alvora Trading Platform

Sistema de trading algorítmico multi-servicio. Monorepo con 3 servicios independientes + cliente de escritorio.

> **ADVERTENCIA**: Proyecto educativo/experimental. No garantiza rentabilidad. El trading con dinero real conlleva riesgo de pérdida total. El modo live está **deshabilitado por defecto** y requiere confirmación explícita.

## Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│  trading-client/  (PC / VPS local)                        │
│  ├── app/            FastAPI + SQLAlchemy + broker + IA   │
│  ├── desktop/        Tauri 2 + React 19 (UI de escritorio)│
│  └── proxy/          Proxy VPS para Binance API           │
├──────────────────────────────────────────────────────────┤
│  auth-server/      (Cloud / VPS)                          │
│  └── app/            FastAPI + PostgreSQL + JWT + Binance Pay │
├──────────────────────────────────────────────────────────┤
│  ai-server/        (Cloud)                                │
│  └── app/            FastAPI + 12 agentes IA + CCXT + HMAC │
└──────────────────────────────────────────────────────────┘
```

| Servicio | Ruta | Puerto | Stack | Rol |
|---|---|---|---|---|
| **Trading Client** | `trading-client/` | 8080 | Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL/SQLite, Tauri 2 | Cliente local: broker, ejecución, datos de mercado, agente IA |
| **Auth Server** | `auth-server/` | 8000 | FastAPI, PostgreSQL, PyJWT, Binance Pay | Auth, suscripciones, licencia JWT, grants de cuota IA |
| **AI Server** | `ai-server/` | 8001 | FastAPI, 12 agentes, CCXT, JSON Schema, HMAC | Análisis IA cloud con router de niveles por plan |

## Estructura del repositorio

```
TRADING PROJECT/
├── trading-client/     # Cliente activo (fuente de verdad)
│   ├── app/            # Backend FastAPI
│   └── desktop/        # Cliente Tauri 2 + React 19 + TypeScript
├── auth-server/        # Servidor de autenticación (VPS)
├── ai-server/          # Servidor de IA (cloud)
├── docs/               # Documentación de arquitectura y migración
├── images/             # Logos y assets
├── models/             # Modelos ML
├── run_server.py       # Launcher de conveniencia para trading-client
└── .github/workflows/  # CI para los 3 servicios
```

## Puesta en marcha rápida

Cada servicio es independiente y tiene su propio `.env.example`, `docker-compose.yml`, `Dockerfile` y `pyproject.toml`/`requirements.txt`. Consulta el `README.md` de cada servicio para detalles.

### Trading Client (local)

```bash
cd trading-client
cp .env.example .env      # edita con tus claves Binance / IA / AUTH_SERVER_URL
docker-compose up -d      # http://localhost:8080
```

O sin Docker, usando el launcher de la raíz:

```bash
python run_server.py
```

El cliente de escritorio (Tauri) se levanta desde:

```bash
cd trading-client/desktop
npm install
npm run dev               # Vite dev server en :1420
```

### Auth Server (VPS)

```bash
cd auth-server
cp .env.example .env
docker-compose up -d      # http://localhost:8000
```

### AI Server (cloud)

```bash
cd ai-server
cp .env.example .env
docker-compose up -d      # http://localhost:8001
```

## Documentación

- `docs/CURRENT_ARCHITECTURE_AUDIT.md` — auditoría de la arquitectura actual con rutas y líneas reales
- `docs/TARGET_ARCHITECTURE.md` — arquitectura objetivo
- `docs/MIGRATION_PLAN.md` — plan de migración por fases
- `docs/SECURITY_REVIEW.md` — revisión de seguridad
- `docs/INTELLIGENCE_PLATFORM_MIGRATION.md` — migración de la plataforma de inteligencia

## CI

El workflow `.github/workflows/ci.yml` ejecuta tests para los 3 servicios en paralelo (trading-client, ai-server, auth-server).
