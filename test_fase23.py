"""Test new Fase 2-3 endpoints with real user authentication."""
import httpx
import json

AUTH_URL = "http://76.13.180.80:8000"
API_URL = "http://76.13.180.80:8080"

# Login
r = httpx.post(f"{AUTH_URL}/api/auth/login", json={
    "email": "nokturnog@gmail.com",
    "password": "panicopain1",
}, timeout=10)
print(f"Login: {r.status_code}")
resp = r.json()
token = resp.get("token")
if not token:
    print(f"  ERROR: No token. Full response: {json.dumps(resp, indent=2)[:500]}")
    exit(1)
print(f"  Token: {token[:30]}...")
headers = {"Authorization": f"Bearer {token}"}

print("=" * 70)
print("FASE 2-3 ENDPOINT TESTS")
print("=" * 70)

tests = [
    # Fase 2: Risk config
    ("GET", "/api/intelligence/risk/config", None, "Get risk config (DB)"),
    ("POST", "/api/intelligence/risk/config", {"max_open_positions": 7}, "Update risk config (DB)"),
    ("GET", "/api/intelligence/risk/status", None, "Get risk status (per-user)"),
    ("GET", "/api/ai-agent/sessions", None, "Get agent sessions"),

    # Fase 3: Preferences
    ("GET", "/api/settings/preferences", None, "Get preferences"),
    ("POST", "/api/settings/preferences", {"theme": "dark", "risk_profile": "aggressive"}, "Save preferences"),
    ("GET", "/api/settings/preferences", None, "Verify preferences saved"),

    # Fase 3: Watchlist
    ("GET", "/api/settings/watchlist", None, "Get watchlist (empty)"),
    ("POST", "/api/settings/watchlist", {"symbol": "BTCUSDT", "display_name": "Bitcoin"}, "Add BTC to watchlist"),
    ("POST", "/api/settings/watchlist", {"symbol": "ETHUSDT", "display_name": "Ethereum"}, "Add ETH to watchlist"),
    ("POST", "/api/settings/watchlist", {"symbol": "SOLUSDT", "display_name": "Solana"}, "Add SOL to watchlist"),
    ("GET", "/api/settings/watchlist", None, "Get watchlist (3 items)"),
    ("PATCH", "/api/settings/watchlist/reorder", {"symbols": ["ETHUSDT", "BTCUSDT", "SOLUSDT"]}, "Reorder watchlist"),
    ("GET", "/api/settings/watchlist", None, "Verify reorder"),
    ("DELETE", "/api/settings/watchlist/SOLUSDT", None, "Remove SOL from watchlist"),
    ("GET", "/api/settings/watchlist", None, "Get watchlist (2 items)"),
]

passed = 0
failed = 0

for method, path, body, desc in tests:
    url = f"{API_URL}{path}"
    try:
        if method == "GET":
            r = httpx.get(url, headers=headers, timeout=10)
        elif method == "POST":
            r = httpx.post(url, headers=headers, json=body, timeout=10)
        elif method == "PATCH":
            r = httpx.patch(url, headers=headers, json=body, timeout=10)
        elif method == "DELETE":
            r = httpx.delete(url, headers=headers, timeout=10)

        status = r.status_code
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text

        if status == 200:
            # Truncate for display
            data_str = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            if len(data_str) > 120:
                data_str = data_str[:120] + "..."
            print(f"  [OK] {method} {path:45s} {status} | {desc}")
            if data_str and data_str != "[]":
                print(f"       Response: {data_str}")
            passed += 1
        else:
            print(f"  [FAIL] {method} {path:45s} {status} | {desc}")
            print(f"       Response: {r.text[:200]}")
            failed += 1
    except Exception as e:
        print(f"  [ERR] {method} {path:45s} {type(e).__name__}: {e}")
        failed += 1

print(f"\n{'=' * 70}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'=' * 70}")
