"""
Comprehensive module test for Alvora Trading Platform.
Tests all API endpoints with timing, simulates user flows, and reports bugs.
"""
import time
import json
import sys
import requests

BASE = "http://76.13.180.80:8080"
AUTH_BASE = "http://76.13.180.80:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJub2t0dXJub2dAZ21haWwuY29tIiwidXNlcm5hbWUiOiJub2sxMTExIiwic3Vic2NyaXB0aW9uIjoicHJlbWl1bSIsImV4cCI6MTc4NzE3Nzk4MX0._oXXQpGRiF1ErSnx3dq-hh756nyUg207XZrrsZ2PZmM"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

results = []
bugs = []

def test(name, method, path, base=None, body=None, expected_status=200, timeout=15):
    """Test an endpoint and record timing + result."""
    b = base or BASE
    url = b + path
    t0 = time.time()
    try:
        if method == "GET":
            r = requests.get(url, headers=HEADERS, timeout=timeout)
        elif method == "POST":
            r = requests.post(url, headers=HEADERS, json=body, timeout=timeout)
        elif method == "PATCH":
            r = requests.patch(url, headers=HEADERS, json=body, timeout=timeout)
        elif method == "DELETE":
            r = requests.delete(url, headers=HEADERS, timeout=timeout)
        else:
            r = requests.request(method, url, headers=HEADERS, json=body, timeout=timeout)
        ms = round((time.time() - t0) * 1000)
        ok = r.status_code == expected_status
        status_icon = "OK" if ok else "FAIL"
        result = {
            "name": name,
            "method": method,
            "path": path,
            "status": r.status_code,
            "expected": expected_status,
            "ms": ms,
            "ok": ok,
        }
        results.append(result)
        try:
            body_preview = r.text[:200]
        except:
            body_preview = ""
        if not ok:
            result["body"] = body_preview
            bugs.append(f"[{status_icon}] {name}: {method} {path} -> {r.status_code} (expected {expected_status}) in {ms}ms\n  Body: {body_preview}")
            print(f"  FAIL {name}: {r.status_code} in {ms}ms - {body_preview[:100]}")
        else:
            print(f"  OK   {name}: {r.status_code} in {ms}ms")
        return r
    except Exception as e:
        ms = round((time.time() - t0) * 1000)
        result = {"name": name, "method": method, "path": path, "status": 0, "expected": expected_status, "ms": ms, "ok": False, "error": str(e)}
        results.append(result)
        bugs.append(f"[FAIL] {name}: {method} {path} -> EXCEPTION: {e} in {ms}ms")
        print(f"  FAIL {name}: EXCEPTION in {ms}ms - {e}")
        return None


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# 1. AUTH MODULE
# ============================================================
section("1. AUTH MODULE")
test("Auth - Verify token (me)", "GET", "/api/auth/me", base=AUTH_BASE)
test("Auth - Login (wrong password)", "POST", "/api/auth/login", base=AUTH_BASE, body={"email": "test@test.com", "password": "wrong"}, expected_status=401)

# ============================================================
# 2. DASHBOARD MODULE
# ============================================================
section("2. DASHBOARD MODULE")
test("Dashboard - Portfolio summary", "GET", "/api/ai-agent/portfolio-summary")
test("Dashboard - Today priorities", "GET", "/api/intelligence/today-priorities")
test("Dashboard - AI activity", "GET", "/api/intelligence/activity")
test("Dashboard - Changes since last visit", "GET", "/api/intelligence/changes-since-last-login")
test("Dashboard - Notifications", "GET", "/api/notifications?unread_only=true&limit=5")
test("Dashboard - Unread count", "GET", "/api/notifications/unread-count")

# ============================================================
# 3. MARKET DATA MODULE
# ============================================================
section("3. MARKET DATA MODULE")
test("Market - Live prices", "GET", "/api/prices/live")
test("Market - BTC price", "GET", "/api/prices/live/BTCUSDT")
test("Market - Movers", "GET", "/api/market/movers")
test("Market - Klines BTCUSDT", "GET", "/api/klines/BTCUSDT?interval=1h&limit=10")
test("Market - Klines ETH/USDT", "GET", "/api/klines/ETH%2FUSDT?interval=1h&limit=10")

# ============================================================
# 4. INTELLIGENCE MODULE
# ============================================================
section("4. INTELLIGENCE MODULE")
test("Intel - Market overview", "GET", "/api/intelligence/market-overview")
test("Intel - Fear & Greed", "GET", "/api/intelligence/fear-greed")
test("Intel - Dominance", "GET", "/api/intelligence/dominance")
test("Intel - News", "GET", "/api/intelligence/news?limit=5")
test("Intel - Daily report", "GET", "/api/intelligence/daily-report")
test("Intel - Signals", "GET", "/api/intelligence/signals/technical?limit=5")
test("Intel - User profile", "GET", "/api/intelligence/profile")
test("Intel - Scheduler status", "GET", "/api/intelligence/scheduler/status")
test("Intel - Sources", "GET", "/api/intelligence/sources")
test("Intel - Analysis", "GET", "/api/intelligence/analysis?limit=5")

# ============================================================
# 5. POSITIONS & TRADING MODULE
# ============================================================
section("5. POSITIONS & TRADING MODULE")
test("Trading - Positions", "GET", "/api/positions")
test("Trading - Orders", "GET", "/api/orders")
test("Trading - Trades", "GET", "/api/trades")
test("Trading - Signals", "GET", "/api/signals")
test("Trading - Snapshots", "GET", "/api/snapshots?limit=5")
test("Trading - Strategy runs", "GET", "/api/strategy-runs?limit=5")
test("Trading - Backtests", "GET", "/api/backtests?limit=5")
test("Trading - Historical data status", "GET", "/api/historical-data/status")

# ============================================================
# 6. BROKER MODULE
# ============================================================
section("6. BROKER MODULE")
test("Broker - Supported brokers", "GET", "/api/brokers")
test("Broker - Connected accounts", "GET", "/api/broker-accounts")
test("Broker - Binance balance", "GET", "/api/binance/balance")
test("Broker - Binance open orders", "GET", "/api/binance/open-orders")
test("Broker - Binance positions", "GET", "/api/binance/positions")
test("Broker - Binance account", "GET", "/api/binance/account")
test("Broker - Binance resumen", "GET", "/api/binance/resumen")
test("Broker - Binance price BTC", "GET", "/api/binance/price?symbol=BTCUSDT")
test("Broker - Broker balance (generic)", "GET", "/api/broker/binance/balance")
test("Broker - Broker positions (generic)", "GET", "/api/broker/binance/positions")

# ============================================================
# 7. AI AGENT MODULE
# ============================================================
section("7. AI AGENT MODULE")
test("AI Agent - Status", "GET", "/api/ai-agent/status")
test("AI Agent - Plan", "GET", "/api/ai-agent/plan")
test("AI Agent - Log", "GET", "/api/ai-agent/log?limit=5")
test("AI Agent - Stats", "GET", "/api/ai-agent/stats")
test("AI Agent - Brokers", "GET", "/api/ai-agent/brokers")
test("AI Agent - Trading mode", "GET", "/api/trading-mode")
test("AI Agent - Symbol settings", "GET", "/api/ai-agent/symbol-settings?symbol=BTCUSDT")
test("AI Agent - Transparency", "GET", "/api/ai-agent/transparency?limit=5")
test("AI Agent - Backtest comparison", "GET", "/api/ai-agent/backtest-comparison")
test("AI Agent - Performance learning", "GET", "/api/ai-agent/performance-learning")
test("AI Agent - Learning insights", "GET", "/api/ai-agent/learning-insights")
test("AI Agent - Sessions", "GET", "/api/ai-agent/sessions?limit=5")

# ============================================================
# 8. ALVORA MODULE
# ============================================================
section("8. ALVORA MODULE")
test("Alvora - Status", "GET", "/api/alvora/status")
test("Alvora - Config", "GET", "/api/alvora/config")
test("Alvora - Quick prompts", "GET", "/api/alvora/quick-prompts")
test("Alvora - Conversations", "GET", "/api/alvora/conversations")

# ============================================================
# 9. PAPER TRADING MODULE
# ============================================================
section("9. PAPER TRADING MODULE")
test("Paper - Status", "GET", "/api/paper-trading/status")

# ============================================================
# 10. SETTINGS MODULE
# ============================================================
section("10. SETTINGS MODULE")
test("Settings - Keys", "GET", "/api/settings/keys")
test("Settings - Watchlist", "GET", "/api/settings/watchlist")
test("Settings - Feature flags", "GET", "/api/settings/feature-flags")

# ============================================================
# 11. STATS MODULE
# ============================================================
section("11. STATS MODULE")
test("Stats - General", "GET", "/api/stats")

# ============================================================
# 12. SOCIAL MODULE
# ============================================================
section("12. SOCIAL MODULE")
test("Social - Leaders", "GET", "/api/social/leaders?limit=5")
test("Social - Leaderboard", "GET", "/api/social/leaderboard?limit=5")
test("Social - Signals feed", "GET", "/api/social/signals/feed?limit=5")
test("Social - My follows", "GET", "/api/social/my-follows")

# ============================================================
# 13. BOTS MODULE
# ============================================================
section("13. BOTS MODULE")
test("Bots - List", "GET", "/api/bots")

# ============================================================
# SUMMARY
# ============================================================
section("SUMMARY")
total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = sum(1 for r in results if not r["ok"])
avg_ms = round(sum(r["ms"] for r in results) / total) if total else 0
slow = [r for r in results if r["ms"] > 2000]

print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
print(f"Average response time: {avg_ms}ms")
print(f"Slow endpoints (>2s): {len(slow)}")
for s in slow:
    print(f"  - {s['name']}: {s['ms']}ms")

if bugs:
    print(f"\n{'='*60}")
    print(f"  BUGS FOUND: {len(bugs)}")
    print(f"{'='*60}")
    for b in bugs:
        print(f"\n{b}")
else:
    print("\nNo bugs found!")

# Save results to file
with open("/tmp/test_results.json", "w") as f:
    json.dump({"results": results, "bugs": bugs, "summary": {"total": total, "passed": passed, "failed": failed, "avg_ms": avg_ms}}, f, indent=2)
print(f"\nResults saved to /tmp/test_results.json")
