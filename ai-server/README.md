# Alvora AI Server

Cloud AI analysis service with 8 specialized agents for trading decisions.

## Architecture

- **FastAPI** service, independent from auth-server and trading-client.
- **8 specialized agents**: Market Analyst, Risk Analyst, Strategy Selector, Entry Strategist, Exit Strategist, Portfolio Manager, Sentiment Analyst, Performance Monitor.
- **Router de niveles**: selects LLM model based on user plan (free/pro/premium).
- **HMAC service-to-service** auth with nonce + timestamp anti-replay.
- **JSON Schema validation** on all LLM outputs before returning to client.
- **Shared cache** to avoid recomputing analysis when data hasn't changed.
- **Token accounting** per user for billing and quota.

## Security

- Never receives broker API keys or sensitive user data.
- JWT validated against Auth Server.
- HMAC signature on every `/v1/` request.
- Timestamp window of 5 minutes.
- Nonce-based replay protection.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/v1/analyze` | Analyze market context (HMAC + JWT required) |
| GET | `/v1/agents` | List available agents |
| GET | `/v1/usage/{user_id_hash}` | Get token usage for a user |
| GET | `/v1/usage` | Get all usage (admin only) |

## Setup

```bash
cp .env.example .env
# Edit .env with your GROQ_API_KEY and HMAC_SECRET
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Docker

```bash
docker-compose up -d
```
