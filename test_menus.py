"""Test endpoints for reports, alerts, positions, SL/TP."""
import httpx

VPS = "http://76.13.180.80"
BACKEND = f"{VPS}:8080"
AUTH = f"{VPS}:8000"

# Login
r = httpx.post(f"{AUTH}/api/auth/login", json={"email": "test@test.com", "password": "test1234"}, timeout=10)
jwt = r.json().get("token")
h = {"Authorization": f"Bearer {jwt}"}

endpoints = [
    "/api/intelligence/reports/all",
    "/api/intelligence/reports/BTC",
    "/api/intelligence/alerts?limit=20",
    "/api/intelligence/price-alerts",
    "/api/positions",
    "/api/intelligence/paper-positions",
    "/api/ai-agent/plan",
    "/api/trading-mode",
    "/api/intelligence/daily-report",
    "/api/intelligence/signals/technical",
    "/api/intelligence/market-overview",
    "/api/intelligence/whale-activity",
    "/api/intelligence/fear-greed",
    "/api/intelligence/dominance",
    "/api/intelligence/news",
    "/api/ai-agent/status",
    "/api/ai-agent/stats",
    "/api/ai-agent/log",
    "/api/ai-agent/brokers",
    "/api/binance/balance",
    "/api/binance/resumen",
    "/api/binance/positions",
    "/api/binance/open-orders",
    "/api/orders?status=open",
    "/api/orders?limit=50",
    "/api/trades?limit=20",
    "/api/market/movers",
    "/api/klines/BTCUSDT?interval=1h&limit=10",
    "/api/prices/live",
    "/api/signals",
    "/api/stats",
    "/api/snapshots?limit=1",
    "/api/paper-trading/status",
]

passed = 0
failed = 0
for ep in endpoints:
    try:
        r = httpx.get(f"{BACKEND}{ep}", headers=h, timeout=15)
        status = r.status_code
        try:
            data = r.json()
        except:
            data = r.text[:150]
        
        ok = status < 400
        if isinstance(data, dict) and "error" in data:
            ok = False
        
        if ok:
            passed += 1
            if isinstance(data, list):
                detail = f"({len(data)} items)"
            elif isinstance(data, dict):
                if "error" in data:
                    detail = data["error"][:80]
                else:
                    detail = f"keys: {list(data.keys())[:5]}"
            else:
                detail = str(data)[:80]
            print(f"[OK] {ep:55s} {status} {detail}")
        else:
            failed += 1
            if isinstance(data, dict):
                detail = str(data.get("detail", data.get("error", "")))[:100]
            else:
                detail = str(data)[:100]
            print(f"[XX] {ep:55s} {status} {detail}")
    except Exception as e:
        failed += 1
        print(f"[XX] {ep:55s} ERR {str(e)[:100]}")

print(f"\n{'='*80}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed+failed}")
