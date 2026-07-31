"""Test all frontend endpoints through Vite proxy with real auth."""
import httpx
import json

# Login
r = httpx.post("http://76.13.180.80:8000/api/auth/login", json={"email": "test@test.com", "password": "test1234"}, timeout=10)
jwt = r.json().get("token")
h = {"Authorization": f"Bearer {jwt}"}

VITE = "http://localhost:1420"

# All endpoints used by Reports, Positions, Alerts pages
endpoints = [
    # Reports page
    "/api/intelligence/reports/all",
    "/api/intelligence/reports/BTC",
    # Alerts page  
    "/api/intelligence/alerts?limit=20",
    "/api/intelligence/price-alerts",
    # Positions (BrokerPage)
    "/api/positions",
    "/api/trading-mode",
    "/api/intelligence/paper-positions",
    "/api/paper-trading/status",
    # AI Agent plan (used by PositionsModule)
    "/api/ai-agent/plan",
    # Binance balance
    "/api/binance/balance",
    # Orders
    "/api/orders?status=open",
    "/api/orders?limit=50",
    # Trades
    "/api/trades?limit=20",
    # Brokers
    "/api/brokers",
    "/api/broker-accounts",
]

print("=== Through Vite Proxy ===")
for ep in endpoints:
    try:
        r = httpx.get(f"{VITE}{ep}", headers=h, timeout=15)
        try:
            data = r.json()
        except:
            data = r.text[:200]
        
        if isinstance(data, list):
            detail = f"({len(data)} items)"
            if len(data) > 0:
                detail += f" first={json.dumps(data[0])[:100]}"
        elif isinstance(data, dict):
            if "error" in data:
                detail = f"ERROR: {data['error'][:100]}"
            elif "detail" in data:
                detail = f"ERROR: {data['detail'][:100]}"
            else:
                detail = f"keys={list(data.keys())[:5]}"
        else:
            detail = str(data)[:100]
            
        status = "OK" if r.status_code < 400 else "XX"
        print(f"  [{status}] {ep:55s} {r.status_code} {detail}")
    except Exception as e:
        print(f"  [XX] {ep:55s} ERR {str(e)[:100]}")
