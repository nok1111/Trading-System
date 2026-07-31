"""Test endpoints through Vite proxy (localhost:1420) to verify frontend routing."""
import httpx

# Login
r = httpx.post("http://76.13.180.80:8000/api/auth/login", json={"email": "test@test.com", "password": "test1234"}, timeout=10)
jwt = r.json().get("token")
h = {"Authorization": f"Bearer {jwt}"}

# Test through Vite proxy
VITE = "http://localhost:1420"
BACKEND = "http://76.13.180.80:8080"

endpoints = [
    "/api/intelligence/reports/all",
    "/api/intelligence/alerts?limit=20",
    "/api/intelligence/price-alerts",
    "/api/positions",
    "/api/trading-mode",
    "/api/intelligence/paper-positions",
    "/api/ai-agent/plan",
    "/api/binance/balance",
]

print("=== Through Vite Proxy (localhost:1420) ===")
for ep in endpoints:
    try:
        r = httpx.get(f"{VITE}{ep}", headers=h, timeout=15)
        print(f"  {ep:55s} {r.status_code} {r.text[:150]}")
    except Exception as e:
        print(f"  {ep:55s} ERR {str(e)[:100]}")

print("\n=== Direct to Backend (76.13.180.80:8080) ===")
for ep in endpoints:
    try:
        r = httpx.get(f"{BACKEND}{ep}", headers=h, timeout=15)
        print(f"  {ep:55s} {r.status_code} {r.text[:150]}")
    except Exception as e:
        print(f"  {ep:55s} ERR {str(e)[:100]}")
