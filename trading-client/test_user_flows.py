"""
User flow simulation — simulates real user interactions step-by-step.
Tests both Alvora and non-Alvora flows.
"""
import time
import json
import requests

BASE = "http://76.13.180.80:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJub2t0dXJub2dAZ21haWwuY29tIiwidXNlcm5hbWUiOiJub2sxMTExIiwic3Vic2NyaXB0aW9uIjoicHJlbWl1bSIsImV4cCI6MTc4NzE3Nzk4MX0._oXXQpGRiF1ErSnx3dq-hh756nyUg207XZrrsZ2PZmM"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

flow_bugs = []

def step(num, desc):
    print(f"\n  Step {num}: {desc}")

def api_call(method, path, body=None, timeout=30):
    url = BASE + path
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
        ms = round((time.time() - t0) * 1000)
        try:
            data = r.json()
        except:
            data = r.text[:200]
        return r.status_code, data, ms
    except Exception as e:
        return 0, str(e), round((time.time() - t0) * 1000)

def check(name, status, data, ms, expected=200):
    ok = status == expected
    icon = "OK" if ok else "FAIL"
    print(f"    [{icon}] {name}: {status} in {ms}ms")
    if not ok:
        preview = json.dumps(data)[:200] if isinstance(data, dict) else str(data)[:200]
        print(f"    Response: {preview}")
        flow_bugs.append(f"{name}: status={status}, data={preview}")
    return ok, data


print("=" * 60)
print("  FLOW 1: User Login -> Dashboard -> View Data")
print("=" * 60)

step(1, "User opens dashboard (parallel data fetch)")
# Dashboard fetches all this in parallel
dashboard_calls = [
    ("GET", "/api/intelligence/profile", None),
    ("GET", "/api/ai-agent/portfolio-summary", None),
    ("GET", "/api/intelligence/market-overview", None),
    ("GET", "/api/intelligence/dominance", None),
    ("GET", "/api/intelligence/daily-report", None),
    ("GET", "/api/intelligence/signals/technical?limit=3", None),
    ("GET", "/api/intelligence/changes-since-last-login", None),
    ("GET", "/api/intelligence/today-priorities", None),
    ("GET", "/api/intelligence/activity", None),
]
for method, path, body in dashboard_calls:
    status, data, ms = api_call(method, path, body)
    check(path.split("?")[0], status, data, ms)

step(2, "User checks positions and balance")
status, data, ms = api_call("GET", "/api/positions")
check("Positions", status, data, ms)
if status == 200 and isinstance(data, list):
    print(f"    Found {len(data)} open positions")
    for p in data[:3]:
        print(f"      - #{p.get('id')} {p.get('symbol')} P&L={p.get('unrealized_pnl')} SL={p.get('stop_loss')} TP={p.get('take_profit')}")

status, data, ms = api_call("GET", "/api/binance/balance")
check("Binance balance", status, data, ms)
if status == 200 and isinstance(data, dict):
    print(f"    Total USD: {data.get('total_usd')}, Assets: {len(data.get('assets', []))}")

print("\n" + "=" * 60)
print("  FLOW 2: Non-Alvora Manual Trade (Paper Trading)")
print("=" * 60)

step(1, "Check paper trading status")
status, data, ms = api_call("GET", "/api/paper-trading/status")
check("Paper status", status, data, ms)

step(2, "Get BTC price for trade")
status, data, ms = api_call("GET", "/api/binance/price?symbol=BTCUSDT")
check("BTC price", status, data, ms)
btc_price = data.get("price") if isinstance(data, dict) else None
print(f"    BTC price: {btc_price}")

step(3, "Execute paper buy order")
status, data, ms = api_call("POST", "/api/ai-agent/execute", {
    "action_type": "buy",
    "symbol": "BTCUSDT",
    "confidence": 0.75,
    "reason": "Manual paper trade test",
    "stop_loss_pct": 3.0,
    "take_profit_pct": 8.0,
    "position_size_usd": 100,
})
check("Paper buy BTCUSDT", status, data, ms)
if status == 200 and isinstance(data, dict):
    print(f"    Result: {json.dumps(data)[:200]}")

step(4, "Verify position was created")
status, data, ms = api_call("GET", "/api/positions")
check("Positions after buy", status, data, ms)
if status == 200 and isinstance(data, list):
    btc_pos = [p for p in data if "BTC" in p.get("symbol", "")]
    print(f"    BTC positions: {len(btc_pos)}")

step(5, "Set stop loss on the position")
if status == 200 and isinstance(data, list) and data:
    pos = data[0]
    pos_id = pos.get("id")
    status2, data2, ms2 = api_call("PATCH", f"/api/positions/{pos_id}/auto-sell", {"enabled": True})
    check(f"Auto-sell on #{pos_id}", status2, data2, ms2)

print("\n" + "=" * 60)
print("  FLOW 3: Alvora Chat -> Action -> Execute")
print("=" * 60)

step(1, "Create new Alvora conversation")
status, data, ms = api_call("POST", "/api/alvora/conversations", {"title": "Test flow"})
check("Create conversation", status, data, ms)
conv_id = data.get("conversation_id") if isinstance(data, dict) else None
print(f"    Conversation ID: {conv_id}")

step(2, "Send message to Alvora asking for opportunities")
status, data, ms = api_call("POST", "/api/alvora/chat", {
    "message": "Hay oportunidades de trading hoy? Dame una concreta con SL y TP.",
    "conversation_id": conv_id,
}, timeout=60)
check("Alvora chat", status, data, ms, expected=200)
if status == 200 and isinstance(data, dict):
    reply = data.get("reply", "")
    actions = data.get("actions", [])
    print(f"    Reply length: {len(reply)} chars")
    print(f"    Actions proposed: {len(actions)}")
    for a in actions:
        print(f"      - {a.get('type')}: {json.dumps(a.get('params', {}))[:100]}")
    
    step(3, "Execute first action if any")
    if actions:
        action = actions[0]
        status2, data2, ms2 = api_call("POST", "/api/alvora/execute", {
            "action_type": action.get("type"),
            "params": action.get("params", {}),
            "conversation_id": conv_id,
        }, timeout=30)
        check(f"Execute {action.get('type')}", status2, data2, ms2)
        if isinstance(data2, dict):
            print(f"    Result: {json.dumps(data2)[:200]}")
    else:
        print("    No actions to execute")

step(4, "Get conversation messages")
status, data, ms = api_call("GET", f"/api/alvora/conversations/{conv_id}/messages" if conv_id else "/api/alvora/conversations")
check("Get messages", status, data, ms)

print("\n" + "=" * 60)
print("  FLOW 4: Alvora Config -> Save -> Test Provider -> Verify")
print("=" * 60)

step(1, "Get current Alvora config")
status, data, ms = api_call("GET", "/api/alvora/config")
check("Get config", status, data, ms)
if status == 200 and isinstance(data, dict):
    print(f"    Provider: {data.get('provider')}")
    print(f"    Model: {data.get('model')}")
    print(f"    Fallback chain: {len(data.get('fallback_chain', []))}")

step(2, "Save config with test values")
status, data, ms = api_call("POST", "/api/alvora/config", {
    "provider": "gemini",
    "language": "es",
    "response_style": "detailed",
    "risk_advice_level": "balanced",
    "auto_suggest_actions": True,
    "max_tokens": 1800,
    "temperature": 0.5,
    "include_positions": True,
    "include_market_data": True,
    "include_profile": True,
    "include_recommendations": True,
})
check("Save config", status, data, ms)

step(3, "Verify config persisted")
status, data, ms = api_call("GET", "/api/alvora/config")
check("Verify config", status, data, ms)
if status == 200 and isinstance(data, dict):
    if data.get("language") != "es":
        flow_bugs.append("Config not persisted: language should be 'es'")
        print(f"    FAIL: Config not persisted correctly")

print("\n" + "=" * 60)
print("  FLOW 5: Broker Operations (without Alvora)")
print("=" * 60)

step(1, "Get broker accounts")
status, data, ms = api_call("GET", "/api/broker-accounts")
check("Broker accounts", status, data, ms)

step(2, "Get broker balance")
status, data, ms = api_call("GET", "/api/broker/binance/balance")
check("Broker balance", status, data, ms)

step(3, "Get broker positions")
status, data, ms = api_call("GET", "/api/broker/binance/positions")
check("Broker positions", status, data, ms)

step(4, "Get broker orders")
status, data, ms = api_call("GET", "/api/broker/binance/orders")
check("Broker orders", status, data, ms)

step(5, "Get broker trades")
status, data, ms = api_call("GET", "/api/broker/binance/trades")
check("Broker trades", status, data, ms)

step(6, "Get broker ticker")
status, data, ms = api_call("GET", "/api/broker/binance/ticker?symbol=BTCUSDT")
check("Broker ticker", status, data, ms)

step(7, "Get broker klines")
status, data, ms = api_call("GET", "/api/broker/binance/klines?symbol=BTCUSDT&interval=1h&limit=10")
check("Broker klines", status, data, ms)

step(8, "Get market movers")
status, data, ms = api_call("GET", "/api/broker/binance/movers")
check("Market movers", status, data, ms)

print("\n" + "=" * 60)
print("  FLOW 6: AI Agent Operations (without Alvora)")
print("=" * 60)

step(1, "Get AI agent status")
status, data, ms = api_call("GET", "/api/ai-agent/status")
check("AI status", status, data, ms)

step(2, "Get AI agent plan")
status, data, ms = api_call("GET", "/api/ai-agent/plan")
check("AI plan", status, data, ms)

step(3, "Get AI agent stats")
status, data, ms = api_call("GET", "/api/ai-agent/stats")
check("AI stats", status, data, ms)

step(4, "Get AI agent transparency")
status, data, ms = api_call("GET", "/api/ai-agent/transparency?limit=5")
check("AI transparency", status, data, ms)

step(5, "Test AI key")
status, data, ms = api_call("POST", "/api/ai-agent/test-key", {
    "provider": "gemini",
    "api_key": "test_invalid_key",
}, timeout=15)
check("Test AI key (invalid)", status, data, ms, expected=200)

print("\n" + "=" * 60)
print("  FLOW 7: Social Trading")
print("=" * 60)

step(1, "Get leaderboard")
status, data, ms = api_call("GET", "/api/social/leaderboard?limit=5")
check("Leaderboard", status, data, ms)

step(2, "Get signals feed")
status, data, ms = api_call("GET", "/api/social/signals/feed?limit=5")
check("Signals feed", status, data, ms)

step(3, "Get my follows")
status, data, ms = api_call("GET", "/api/social/my-follows")
check("My follows", status, data, ms)

print("\n" + "=" * 60)
print("  FLOW 8: Settings & Preferences")
print("=" * 60)

step(1, "Get user keys")
status, data, ms = api_call("GET", "/api/settings/keys")
check("Settings keys", status, data, ms)

step(2, "Get watchlist")
status, data, ms = api_call("GET", "/api/settings/watchlist")
check("Watchlist", status, data, ms)

step(3, "Get user profile")
status, data, ms = api_call("GET", "/api/intelligence/profile")
check("User profile", status, data, ms)

step(4, "Save user profile")
status, data, ms = api_call("POST", "/api/intelligence/profile", {
    "risk_tolerance": "aggressive",
    "experience_level": "advanced",
    "trading_goal": "growth",
    "preferred_strategies": ["swing", "scalping"],
    "capital_range": "$1000-$5000",
})
check("Save profile", status, data, ms)

print("\n" + "=" * 60)
print("  FLOW 9: Notifications")
print("=" * 60)

step(1, "Get notifications")
status, data, ms = api_call("GET", "/api/notifications?limit=10")
check("Notifications", status, data, ms)

step(2, "Get unread count")
status, data, ms = api_call("GET", "/api/notifications/unread-count")
check("Unread count", status, data, ms)

step(3, "Mark all as read")
status, data, ms = api_call("POST", "/api/notifications/read-all")
check("Mark all read", status, data, ms)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("  FLOW SIMULATION SUMMARY")
print("=" * 60)

if flow_bugs:
    print(f"\n  BUGS FOUND: {len(flow_bugs)}")
    for b in flow_bugs:
        print(f"    - {b}")
else:
    print("\n  All flows completed without bugs!")

print(f"\n  Total flow bugs: {len(flow_bugs)}")
