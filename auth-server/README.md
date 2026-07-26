# Alvora Auth Server

Cloud-based authentication server for the Alvora trading platform.

## Responsibilities

- User registration and login (JWT)
- Subscription management (free / pro / premium)
- Binance Pay payment processing
- License validation for Trading Clients

## Running with Docker

```bash
# Copy .env.example and edit values
cp .env.example .env

# Start PostgreSQL + Auth Server
docker-compose up -d

# The server will be available at http://localhost:8000
```

## Running locally (without Docker)

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use .env file)
export DATABASE_URL=postgresql+psycopg2://alvora:alvora@localhost:5432/alvora_auth
export JWT_SECRET=your-secret-here

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Auth
- `POST /api/auth/register` — Register new user
- `POST /api/auth/login` — Login, returns JWT
- `GET /api/auth/me` — Get current user info

### Payments
- `POST /api/payments/create` — Create Binance Pay order
- `GET /api/payments/status/{order_id}` — Check payment status
- `GET /api/payments/plans` — List available plans
- `POST /api/payments/webhook` — Binance Pay webhook

### License
- `POST /api/license/validate` — Validate JWT and subscription (used by Trading Client)
- `GET /api/license/check` — GET version of license validation

### Health
- `GET /health` — Server health check
