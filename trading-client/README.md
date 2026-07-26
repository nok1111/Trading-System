# Alvora Trading Client

Local trading client for the Alvora platform. Runs on your PC or VPS via Docker.

## Privacy First

Your Binance API keys and AI provider keys are stored **only** in your local `.env` file.
They are **never** sent to the Auth Server or any cloud service.

## Prerequisites

1. **Docker** — Install from [docker.com](https://docker.com)
2. **Alvora account** — Register at the Alvora Auth Server web (e.g., `https://auth.alvora.io`)

## Quick Start

```bash
# 1. Copy the example env file and edit with your keys
cp .env.example .env
# Edit .env with your Binance API keys, AI provider keys, and Auth Server URL

# 2. Start the Trading Client
docker-compose up -d

# 3. Open the dashboard
# Go to http://localhost:8080/dashboard
# Login with your Alvora account credentials
```

## Configuration

Edit `.env` with your settings:

| Variable | Description | Required |
|----------|-------------|----------|
| `AUTH_SERVER_URL` | URL of the Alvora Auth Server | Yes |
| `BROKER_API_KEY` | Your Binance API key | For live trading |
| `BROKER_API_SECRET` | Your Binance API secret | For live trading |
| `GEMINI_API_KEY` | Google Gemini API key | For AI agent |
| `GROQ_API_KEY` | Groq API key | Alternative AI provider |
| `TRADING_MODE` | `paper` or `live` | Yes |
| `DEFAULT_SYMBOLS` | Comma-separated trading pairs | Yes |

## How It Works

1. **Login**: The dashboard sends your credentials to the Auth Server and receives a JWT
2. **License check**: Every API request is validated against the Auth Server
3. **Trading**: The AI agent uses your local Binance keys to execute trades
4. **Data**: All trades, positions, and signals are stored in local SQLite

## Deploy on a VPS (24/7)

```bash
# SSH into your VPS
ssh user@your-vps

# Clone the repo and navigate to the trading client
cd alvora/trading-client

# Configure
cp .env.example .env
nano .env  # Set your keys and AUTH_SERVER_URL

# Start
docker-compose up -d

# The client will run 24/7, automatically restarting if it crashes
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Your PC / VPS (Docker)                      │
│  ├── Trading Client (localhost:8080)         │
│  │   ├── Dashboard (login via Auth Server)   │
│  │   ├── AI Agent + Broker + Execution       │
│  │   ├── SQLite (trades, positions, etc.)    │
│  │   └── .env (Binance keys, AI keys)        │
│  └── Never sends API keys to cloud           │
└──────────────────┬──────────────────────────┘
                   │ HTTPS (license validation)
                   ▼
┌─────────────────────────────────────────────┐
│  Alvora Auth Server (Cloud)                  │
│  ├── User auth + subscription management     │
│  └── PostgreSQL (users, payments)            │
└─────────────────────────────────────────────┘
```
