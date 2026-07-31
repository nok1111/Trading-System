"""Test with real user account to check reports, alerts, positions, SL/TP."""
import httpx
import json

VPS = "http://76.13.180.80"
BACKEND = f"{VPS}:8080"
AUTH = f"{VPS}:8000"

# Login with real account
r = httpx.post(f"{AUTH}/api/auth/login", json={"email": "nokturnog@gmail.com", "password": "panicopain1"}, timeout=10)
print(f"Login: {r.status_code}")
resp = r.json()
print(f"  Response keys: {list(resp.keys())}")
jwt = resp.get("token")
if not jwt:
    print(f"  ERROR: No token. Full response: {json.dumps(resp, indent=2)[:500]}")
    exit(1)

print(f"  Token: {jwt[:30]}...")
h = {"Authorization": f"Bearer {jwt}"}

# Get user info from token
r2 = httpx.post(f"{AUTH}/api/license/validate", headers=h, timeout=10)
print(f"\nLicense validate: {r2.status_code}")
license_info = r2.json()
print(f"  User ID: {license_info.get('user_id')}")
print(f"  Email: {license_info.get('email')}")
print(f"  Subscription: {license_info.get('subscription')}")
print(f"  Valid: {license_info.get('valid')}")

# Test all relevant endpoints
endpoints = [
    "/api/intelligence/reports/all",
    "/api/intelligence/reports/BTC",
    "/api/intelligence/alerts?limit=20",
    "/api/intelligence/price-alerts",
    "/api/positions",
    "/api/trading-mode",
    "/api/intelligence/paper-positions",
    "/api/ai-agent/plan",
    "/api/ai-agent/stats",
    "/api/ai-agent/log",
    "/api/binance/balance",
    "/api/binance/resumen",
    "/api/orders?status=open",
    "/api/orders?limit=50",
    "/api/trades?limit=20",
    "/api/broker-accounts",
    "/api/brokers",
    "/api/paper-trading/status",
    "/api/stats",
    "/api/snapshots?limit=1",
]

print(f"\n{'='*100}")
print(f"ENDPOINT TESTS")
print(f"{'='*100}")
for ep in endpoints:
    try:
        r = httpx.get(f"{BACKEND}{ep}", headers=h, timeout=15)
        try:
            data = r.json()
        except:
            data = r.text[:200]
        
        if isinstance(data, list):
            detail = f"({len(data)} items)"
            if len(data) > 0:
                detail += f" | first={json.dumps(data[0], default=str)[:150]}"
        elif isinstance(data, dict):
            if "error" in data:
                detail = f"ERROR: {data['error'][:120]}"
            elif "detail" in data:
                detail = f"ERROR: {data['detail'][:120]}"
            else:
                detail = f"keys={list(data.keys())[:6]}"
        else:
            detail = str(data)[:120]
            
        status = "OK" if r.status_code < 400 else "XX"
        print(f"  [{status}] {ep:55s} {r.status_code} {detail}")
    except Exception as e:
        print(f"  [XX] {ep:55s} ERR {str(e)[:120]}")
