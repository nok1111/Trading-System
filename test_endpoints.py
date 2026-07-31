"""Test all backend endpoints + Binance proxy to find what's broken."""
import httpx
import json
import sys
import hmac
import hashlib
import time as _time

VPS = "http://76.13.180.80"
BACKEND = f"{VPS}:8080"
AUTH = f"{VPS}:8000"
AI = f"{VPS}:8001"
PROXY = f"{VPS}:9100"

API_KEY = "F4TCPBagEXnIMtjDeOFqnEFIlmV2tHjB1593lxfe6sZ0JO9lpt5AFL8vAEWTD6Ub"
API_SECRET = "rYU23jE5TtzFprTA7lYjvvO1CZ39silzh4DjscCMNNkO5mDZxddn6ctWXVHUCGXG"
PROXY_TOKEN = "9448c6314b9a70f270728f4fadf7f0cee73d643481094a56b52d6aed2f76de4c"

def signed_proxy(method, path, params=None):
    params = params or {}
    params["timestamp"] = int(_time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    body = {
        "method": method,
        "path": path,
        "params": params,
        "api_key_header": API_KEY,
        "testnet": False,
    }
    r = httpx.post(
        f"{PROXY}/proxy",
        json=body,
        headers={"Authorization": f"Bearer {PROXY_TOKEN}"},
        timeout=15,
    )
    return r

def public_proxy(method, path, params=None):
    body = {
        "method": method,
        "path": path,
        "params": params or {},
        "api_key_header": "",
        "testnet": False,
    }
    r = httpx.post(
        f"{PROXY}/proxy",
        json=body,
        headers={"Authorization": f"Bearer {PROXY_TOKEN}"},
        timeout=15,
    )
    return r

def test(name, url, method="GET", json_body=None, headers=None):
    try:
        h = headers or {}
        if method == "GET":
            r = httpx.get(url, headers=h, timeout=15)
        elif method == "POST":
            r = httpx.post(url, json=json_body, headers=h, timeout=15)
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
                keys = list(data.keys())[:5]
                detail = f"keys: {keys}"
        elif isinstance(data, list):
            detail = f"({len(data)} items)"
        else:
            detail = str(data)[:120]
        print(f"[{emoji}] {name:50s} {status} {detail}")
        return ok
    except Exception as e:
        print(f"[XX] {name:50s} ERR {str(e)[:120]}")
        return False

def test_proxy(name, method, path, params=None, signed=True):
    try:
        if signed:
            r = signed_proxy(method, path, params)
        else:
            r = public_proxy(method, path, params)
        status = r.status_code
        try:
            data = r.json()
        except:
            data = r.text[:200]
        ok = status < 400
        if isinstance(data, dict) and ("code" in data and isinstance(data.get("code"), int) and data.get("code", 0) < 0):
            ok = False
        emoji = "OK" if ok else "XX"
        detail = ""
        if isinstance(data, dict):
            if "code" in data and isinstance(data.get("code"), int) and data.get("code", 0) < 0:
                detail = f"code={data.get('code')}: {data.get('msg', '')[:100]}"
            elif "balances" in data:
                nonzero = [b for b in data["balances"] if float(b["free"]) > 0]
                detail = f"{len(nonzero)} non-zero balances"
            elif isinstance(data, list):
                detail = f"({len(data)} items)"
            else:
                keys = list(data.keys())[:5]
                detail = f"keys: {keys}"
        elif isinstance(data, list):
            detail = f"({len(data)} items)"
        else:
            detail = str(data)[:120]
        print(f"[{emoji}] {name:50s} {status} {detail}")
        return ok
    except Exception as e:
        print(f"[XX] {name:50s} ERR {str(e)[:120]}")
        return False

print("=" * 110)
print("HEALTH CHECKS")
print("=" * 110)
test("Backend health", f"{BACKEND}/health")
test("Auth health", f"{AUTH}/health")
test("AI health", f"{AI}/health")
test("Proxy health", f"{PROXY}/health")

print()
print("=" * 110)
print("AUTH - Login")
print("=" * 110)
jwt = None
for email, pwd in [
    ("nokturno@test.com", "test1234"),
    ("admin@test.com", "admin"),
    ("test@test.com", "test1234"),
]:
    try:
        r = httpx.post(f"{AUTH}/api/auth/login", json={"email": email, "password": pwd}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            jwt = data.get("token") or data.get("access_token")
            print(f"[OK] Login OK as {email}, JWT: {jwt[:30]}...")
            break
        else:
            print(f"  Try {email}: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"  Try {email}: ERR {e}")

if not jwt:
    print("  No login worked, registering test user...")
    r = httpx.post(f"{AUTH}/api/auth/register", json={"email": "test@test.com", "username": "test", "password": "test1234"}, timeout=10)
    print(f"  Register: {r.status_code} {r.text[:200]}")
    if r.status_code == 200:
        jwt = r.json().get("token")
        print(f"[OK] Registered, JWT: {jwt[:30]}...")

auth_headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

print()
print("=" * 110)
print("BACKEND ENDPOINTS (with JWT)")
print("=" * 110)

test("GET /api/binance/balance", f"{BACKEND}/api/binance/balance", headers=auth_headers)
test("GET /api/binance/price?symbol=BTCUSDT", f"{BACKEND}/api/binance/price?symbol=BTCUSDT", headers=auth_headers)
test("GET /api/binance/positions", f"{BACKEND}/api/binance/positions", headers=auth_headers)
test("GET /api/snapshots?limit=1", f"{BACKEND}/api/snapshots?limit=1", headers=auth_headers)
test("GET /api/positions", f"{BACKEND}/api/positions", headers=auth_headers)
test("GET /api/orders?status=open", f"{BACKEND}/api/orders?status=open", headers=auth_headers)
test("GET /api/orders?limit=50", f"{BACKEND}/api/orders?limit=50", headers=auth_headers)
test("GET /api/trades?limit=20", f"{BACKEND}/api/trades?limit=20", headers=auth_headers)
test("GET /api/intelligence/market-overview", f"{BACKEND}/api/intelligence/market-overview", headers=auth_headers)
test("GET /api/intelligence/whale-activity", f"{BACKEND}/api/intelligence/whale-activity", headers=auth_headers)
test("GET /api/intelligence/paper-positions", f"{BACKEND}/api/intelligence/paper-positions", headers=auth_headers)
test("GET /api/intelligence/fear-greed", f"{BACKEND}/api/intelligence/fear-greed", headers=auth_headers)
test("GET /api/intelligence/dominance", f"{BACKEND}/api/intelligence/dominance", headers=auth_headers)
test("GET /api/intelligence/news", f"{BACKEND}/api/intelligence/news", headers=auth_headers)
test("GET /api/intelligence/signals/technical", f"{BACKEND}/api/intelligence/signals/technical", headers=auth_headers)
test("GET /api/intelligence/daily-report", f"{BACKEND}/api/intelligence/daily-report", headers=auth_headers)
test("GET /api/ai-agent/status", f"{BACKEND}/api/ai-agent/status", headers=auth_headers)
test("GET /api/ai-agent/stats", f"{BACKEND}/api/ai-agent/stats", headers=auth_headers)
test("GET /api/ai-agent/log", f"{BACKEND}/api/ai-agent/log", headers=auth_headers)
test("GET /api/ai-agent/plan", f"{BACKEND}/api/ai-agent/plan", headers=auth_headers)
test("GET /api/paper-trading/status", f"{BACKEND}/api/paper-trading/status", headers=auth_headers)
test("GET /api/market/movers", f"{BACKEND}/api/market/movers", headers=auth_headers)
test("GET /api/stats/summary", f"{BACKEND}/api/stats/summary", headers=auth_headers)
test("GET /api/klines/BTCUSDT?interval=1h&limit=10", f"{BACKEND}/api/klines/BTCUSDT?interval=1h&limit=10", headers=auth_headers)

print()
print("=" * 110)
print("BINANCE PROXY (direct)")
print("=" * 110)

test_proxy("GET /api/v3/account (signed)", "GET", "/api/v3/account")
test_proxy("GET /api/v3/openOrders (signed)", "GET", "/api/v3/openOrders")
test_proxy("GET /api/v3/openOrders?symbol=BTCUSDT", "GET", "/api/v3/openOrders", {"symbol": "BTCUSDT"})
test_proxy("GET /api/v3/ticker/price?symbol=BTCUSDT (public)", "GET", "/api/v3/ticker/price", {"symbol": "BTCUSDT"}, signed=False)
test_proxy("GET /api/v3/exchangeInfo?symbol=BTCUSDT (public)", "GET", "/api/v3/exchangeInfo", {"symbol": "BTCUSDT"}, signed=False)
test_proxy("GET /api/v3/ticker/24hr?symbol=BTCUSDT (public)", "GET", "/api/v3/ticker/24hr", {"symbol": "BTCUSDT"}, signed=False)
test_proxy("GET /api/v3/klines?symbol=BTCUSDT (public)", "GET", "/api/v3/klines", {"symbol": "BTCUSDT", "interval": "1h", "limit": "5"}, signed=False)

print()
print("=" * 110)
print("DONE")
print("=" * 110)
