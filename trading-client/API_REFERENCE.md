# Alvora Trading Platform — API Reference

## Authentication

All endpoints (except auth and health) require a JWT token:
```
Authorization: Bearer <token>
```

Token obtained from `POST /api/auth/login`.

---

## Auth Server (port 8001)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login (email + password) |
| POST | `/api/auth/verify-2fa` | Verify TOTP code |
| POST | `/api/auth/enable-2fa` | Enable 2FA (returns QR + secret) |
| POST | `/api/auth/disable-2fa` | Disable 2FA |
| POST | `/api/auth/refresh` | Refresh JWT token |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/logout` | Logout (invalidate session) |

---

## Trading Client (port 8000)

### Health & Observability
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Full health check (all deps) |
| GET | `/api/health/live` | Liveness probe |
| GET | `/api/health/ready` | Readiness probe |
| GET | `/api/audit/logs` | Audit logs (filter by source, level) |
| GET | `/api/audit/summary` | Audit summary (24h) |
| GET | `/api/attribution` | Performance attribution |
| GET | `/api/cache/stats` | Cache monitoring |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/overview` | Unified portfolio across brokers |
| GET | `/api/portfolio/positions` | All open positions |
| GET | `/api/portfolio/balances` | Balances per broker |
| GET | `/api/portfolio/exposure` | Net exposure analysis |

### Brokers
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/brokers` | List available brokers |
| GET | `/api/brokers/accounts` | User's connected broker accounts |
| POST | `/api/brokers/connect` | Connect a broker account |
| DELETE | `/api/brokers/accounts/{id}` | Disconnect broker |
| POST | `/api/brokers/validate` | Validate broker credentials |
| GET | `/api/broker-data/ticker/{symbol}` | Get ticker for symbol |
| GET | `/api/broker-data/klines/{symbol}` | Get klines/candles |
| GET | `/api/broker-data/orderbook/{symbol}` | Get order book |

### Trading
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/trading/order` | Place order (market, limit) |
| POST | `/api/trading/cancel` | Cancel order |
| GET | `/api/trading/orders` | List orders |
| GET | `/api/trading/positions` | List open positions |
| GET | `/api/trading/backtests` | List backtest runs |
| GET | `/api/trading/backtests/{id}` | Get backtest run details |

### AI Copilot
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/copilot/chat` | Chat with AI copilot |
| POST | `/api/copilot/suggest` | Get AI suggestions |
| POST | `/api/copilot/quick-action` | Execute quick action |
| GET | `/api/copilot/transparency` | AI transparency log |

### Intelligence & Backtesting
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/intelligence/status` | Intelligence platform status |
| POST | `/api/intelligence/analyze` | Analyze market |
| POST | `/api/intelligence/backtest/run` | Run backtest |
| POST | `/api/intelligence/backtest/optimize` | Optimize strategy params |
| POST | `/api/intelligence/backtest/monte-carlo` | Monte Carlo simulation |
| POST | `/api/intelligence/backtest/compare` | Compare strategies |
| POST | `/api/intelligence/backtest/auto-assign` | Auto-assign best strategy |

### Social Trading
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/social/leaders` | List leaders |
| GET | `/api/social/leaderboard` | Leaderboard |
| POST | `/api/social/follow` | Follow a leader |
| POST | `/api/social/unfollow` | Unfollow |
| GET | `/api/social/signals` | Signal feed |
| POST | `/api/social/signals/{id}/copy` | Copy a signal manually |
| POST | `/api/social/auto-copy/configure` | Configure auto-copy |
| GET | `/api/social/auto-copy/stats` | Auto-copy statistics |
| GET | `/api/social/auto-copy/follows` | List auto-copy follows |

### DCA Bots
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dca/bots` | List DCA bots |
| POST | `/api/dca/bots` | Create DCA bot |
| GET | `/api/dca/bots/{id}` | Get DCA bot |
| POST | `/api/dca/bots/{id}/stop` | Stop DCA bot |
| DELETE | `/api/dca/bots/{id}` | Delete DCA bot |

### Smart Alerts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/smart-alerts` | Get AI-powered alerts |
| POST | `/api/smart-alerts/{id}/dismiss` | Dismiss alert |

### Cache
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cache/stats` | Cache statistics (hit rate, size) |
| POST | `/api/cache/invalidate` | Invalidate cache entries |

---

## Rate Limits

| Endpoint group | Limit | Window |
|----------------|-------|--------|
| `/api/auth/login` | 10 | 60s |
| `/api/auth/register` | 5 | 60s |
| `/api/auth/verify-2fa` | 10 | 60s |
| `/api/trading/order` | 30 | 60s |
| `/api/trading/cancel` | 30 | 60s |
| `/api/brokers/validate` | 5 | 60s |
| `/api/copilot/chat` | 20 | 60s |
| `/api/copilot/suggest` | 10 | 60s |
| Default | 100 | 60s |

Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` (on 429).

---

## WebSocket

| Path | Description |
|------|-------------|
| `/ws/prices` | Real-time price stream |
| `/ws/portfolio` | Portfolio updates |
| `/ws/signals` | Social signal feed (live) |

---

## Error format

```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "retry_after": 30
}
```

HTTP status codes: 200 (success), 400 (bad request), 401 (unauthorized), 403 (forbidden),
404 (not found), 429 (rate limited), 500 (server error), 503 (service unavailable).
