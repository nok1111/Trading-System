"""Test all endpoints with proper user + Binance credentials."""
import httpx
import json
import hmac
import hashlib
import time as _time

VPS = "http://76.13.180.80"
BACKEND = f"{VPS}:8080"
AUTH = f"{VPS}:8000"
PROXY = f"{VPS}:9100"

API_KEY = "F4TCPBagEXnIMtjDeOFqnEFIlmV2tHjB1593lxfe6sZ0JO9lpt5AFL8vAEWTD6Ub"
API_SECRET = "rYU23jE5TtzFprTA7lYjvvO1CZ39silzh4DjscCMNNkO5mDZxddn6ctWXVHUCGXG"
PROXY_TOKEN = "9448c6314b9a70f270728f4fadf7f0cee73d643481094a56b52d6aed2f76de4c"

def test(name, url, method="GET", json_body=None, headers=None):
    try:
        h = headers or {}
        if method == "GET":
            r = httpx.get(url, headers=h, timeout=15)
        elif method == "POST":
            r = httpx.post(url, json=json_body, headers=h, timeout=15)
        elif method == "DELETE":
            r = httpx.delete(url, headers=h, timeout=15)
        status = r.status_code
        try:
            data = r.json()
        except:
            data = r.text[:200]
        ok = status < 400
        if isinstance(data, dict) and "error" in data:
            ok = False
        emoji = "OK" if ok else "XX"
        detail = ""
        if isinstance(data, dict):
            if "error" in data:
                detail = str(data["error"])[:120]
            elif "detail" in data:
                detail = str(data["detail"])[:120]
            elif isinstance(data, list):
                detail = f"({len(data)} items)"
            else:
                keys = list(data.keys())[:6]
                detail = f"keys: {keys}"
        elif isinstance(data, list):
            detail = f"({len(data)} items)"
        else:
            detail = str(data)[:120]
        print(f"[{emoji}] {name:55s} {status} {detail}")
        return ok, data
    except Exception as e:
        print(f"[XX] {name:55s} ERR {str(e)[:120]}")
        return False, None

# Step 1: Login or register
print("=" * 110)
print("STEP 1: AUTH")
print("=" * 110)
jwt = None
# Try login with existing user
r = httpx.post(f"{AUTH}/api/auth/login", json={"email": "test@test.com", "password": "test1234"}, timeout=10)
if r.status_code == 200:
    jwt = r.json().get("token")
    print(f"[OK] Login as test@test.com")
else:
    r = httpx.post(f"{AUTH}/api/auth/register", json={"email": "test@test.com", "username": "test", "password": "test1234"}, timeout=10)
    if r.status_code == 200:
        jwt = r.json().get("token")
        print(f"[OK] Registered test@test.com")

auth_headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}
print(f"JWT: {jwt[:30]}..." if jwt else "NO JWT!")

# Step 2: Save Binance credentials
print()
print("=" * 110)
print("STEP 2: SAVE BINANCE CREDENTIALS")
print("=" * 110)
ok, data = test("POST /api/broker-accounts (save Binance keys)", 
    f"{BACKEND}/api/broker-accounts",
    method="POST",
    json_body={
        "brokerId": "binance",
        "apiKey": API_KEY,
        "apiSecret": API_SECRET,
        "displayName": "Test Binance",
        "environment": "live",
    },
    headers=auth_headers)

# Step 3: Test all endpoints that need credentials
print()
print("=" * 110)
print("STEP 3: TEST ALL ENDPOINTS WITH CREDENTIALS")
print("=" * 110)

endpoints = [
    ("GET /api/binance/balance", "/api/binance/balance"),
    ("GET /api/binance/positions", "/api/binance/positions"),
    ("GET /api/binance/price?symbol=BTCUSDT", "/api/binance/price?symbol=BTCUSDT"),
    ("GET /api/binance/account", "/api/binance/account"),
    ("GET /api/broker-accounts", "/api/broker-accounts"),
    ("GET /api/broker-accounts/binance/credentials", "/api/broker-accounts/binance/credentials"),
    ("GET /api/snapshots?limit=1", "/api/snapshots?limit=1"),
    ("GET /api/positions", "/api/positions"),
    ("GET /api/orders?status=open", "/api/orders?status=open"),
    ("GET /api/orders?limit=50", "/api/orders?limit=50"),
    ("GET /api/trades?limit=20", "/api/trades?limit=20"),
    ("GET /api/intelligence/market-overview", "/api/intelligence/market-overview"),
    ("GET /api/intelligence/whale-activity", "/api/intelligence/whale-activity"),
    ("GET /api/intelligence/paper-positions", "/api/intelligence/paper-positions"),
    ("GET /api/intelligence/fear-greed", "/api/intelligence/fear-greed"),
    ("GET /api/intelligence/dominance", "/api/intelligence/dominance"),
    ("GET /api/intelligence/news", "/api/intelligence/news"),
    ("GET /api/intelligence/signals/technical", "/api/intelligence/signals/technical"),
    ("GET /api/intelligence/daily-report", "/api/intelligence/daily-report"),
    ("GET /api/ai-agent/status", "/api/ai-agent/status"),
    ("GET /api/ai-agent/stats", "/api/ai-agent/stats"),
    ("GET /api/ai-agent/log", "/api/ai-agent/log"),
    ("GET /api/ai-agent/plan", "/api/ai-agent/plan"),
    ("GET /api/paper-trading/status", "/api/paper-trading/status"),
    ("GET /api/market/movers", "/api/market/movers"),
    ("GET /api/klines/BTCUSDT?interval=1h&limit=10", "/api/klines/BTCUSDT?interval=1h&limit=10"),
    ("GET /api/ai-agent/broker", "/api/ai-agent/broker"),
    ("GET /api/ai-agent/brokers", "/api/ai-agent/brokers"),
    ("GET /api/brokers", "/api/brokers"),
]

passed = 0
failed = 0
for name, path in endpoints:
    ok, data = test(name, f"{BACKEND}{path}", headers=auth_headers)
    if ok:
        passed += 1
    else:
        failed += 1

print()
print("=" * 110)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed+failed}")
print("=" * 110)
