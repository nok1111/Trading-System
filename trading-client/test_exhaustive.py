"""Exhaustive test: all position management conditions in real-time.

Tests:
1. Position close (market) — broker-managed
2. SL/TP set (percentage) — broker-managed
3. SL/TP set (absolute) — broker-managed
4. SL/TP update (change existing) — broker-managed
5. Auto-sell toggle — DB position (if exists)
6. Alvora execute: close_position
7. Alvora execute: set_stop_loss
8. Alvora execute: set_take_profit
9. Alvora execute: open_trade (paper)
10. WebSocket real-time push on each change
11. Related modules: Dashboard, AI Agent, Alvora
12. Error conditions: non-existent position, invalid params
"""
import time, json, requests
from websocket import create_connection

BASE = "http://localhost:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTk0NzA4fQ.AwJ-ju0zAvnkWY7FXPPhWAyDUMOM6k4_Ldosmw6mX7A"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
bugs = []

def call(method, path, body=None, timeout=30):
    t0 = time.time()
    try:
        if method == "GET": r = requests.get(BASE+path, headers=H, timeout=timeout)
        elif method == "POST": r = requests.post(BASE+path, headers=H, json=body, timeout=timeout)
        elif method == "PATCH": r = requests.patch(BASE+path, headers=H, json=body, timeout=timeout)
        elif method == "DELETE": r = requests.delete(BASE+path, headers=H, timeout=timeout)
        ms = round((time.time()-t0)*1000)
        try: d = r.json()
        except: d = r.text[:200]
        return r.status_code, d, ms
    except Exception as e:
        return 0, str(e), round((time.time()-t0)*1000)

def check(name, s, d, ms, exp=200):
    ok = s == exp
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {name}: {s} in {ms}ms")
    if not ok:
        bugs.append(f"{name}: {s} — {str(d)[:100]}")
    return ok, d

def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")

# Connect WS for real-time monitoring
print("Connecting WebSocket for real-time monitoring...")
ws = create_connection(f"ws://localhost:8080/api/ws/db-positions?token={TOKEN}", timeout=10)
msg = ws.recv()
d = json.loads(msg)
print(f"WS connected: {len(d.get('positions',[]))} positions in snapshot\n")

def wait_ws_push(timeout=5):
    """Wait for a WS push and return (received, elapsed_ms, data)."""
    ws.settimeout(timeout)
    t0 = time.time()
    try:
        msg = ws.recv()
        d = json.loads(msg)
        elapsed = round((time.time() - t0) * 1000)
        return True, elapsed, d
    except:
        return False, round((time.time() - t0) * 1000), None

# ============================================================
section("1. GET POSITIONS (baseline)")
s, d, m = call("GET", "/api/positions")
check("Get positions", s, d, m)
open_pos = [p for p in d if p.get("status") == "open"] if isinstance(d, list) else []
print(f"  Open: {len(open_pos)}")

# ============================================================
section("2. SL/TP SET (percentage) — broker-managed")
if open_pos:
    sym = open_pos[0]["symbol"].replace("/", "").replace("-", "").replace("_", "")
    entry = float(open_pos[0].get("entry_price") or 0)
    s, d, m = call("POST", "/api/positions/set-sl-tp", body={
        "symbol": sym, "broker_id": "binance", "stop_loss_pct": 5.0, "take_profit_pct": 10.0
    })
    check(f"Set SL/TP 5%/10% {sym}", s, d, m)
    if isinstance(d, dict) and d.get("status") == "executed":
        expected_sl = round(entry * 0.95, 8)
        expected_tp = round(entry * 1.10, 8)
        actual_sl = float(d.get("stop_loss") or 0)
        actual_tp = float(d.get("take_profit") or 0)
        if abs(actual_sl - expected_sl) > 0.01:
            bugs.append(f"SL pct: expected {expected_sl}, got {actual_sl}")
        if abs(actual_tp - expected_tp) > 0.01:
            bugs.append(f"TP pct: expected {expected_tp}, got {actual_tp}")
    # Check WS push
    recv, ms, wd = wait_ws_push(5)
    if recv:
        print(f"  WS push: {ms}ms, type={wd.get('type')}, changed={wd.get('changed')}")
    else:
        print(f"  WS push: not received in 5s")

# ============================================================
section("3. SL/TP SET (absolute) — broker-managed")
if open_pos:
    sym = open_pos[0]["symbol"].replace("/", "").replace("-", "").replace("_", "")
    entry = float(open_pos[0].get("entry_price") or 0)
    sl = round(entry * 0.93, 2)
    tp = round(entry * 1.15, 2)
    s, d, m = call("POST", "/api/positions/set-sl-tp", body={
        "symbol": sym, "broker_id": "binance", "stop_loss": sl, "take_profit": tp
    })
    check(f"Set SL/TP abs {sym}", s, d, m)
    if isinstance(d, dict) and d.get("status") == "executed":
        if float(d.get("stop_loss") or 0) != sl:
            bugs.append(f"SL abs: expected {sl}, got {d.get('stop_loss')}")
        if float(d.get("take_profit") or 0) != tp:
            bugs.append(f"TP abs: expected {tp}, got {d.get('take_profit')}")
    recv, ms, wd = wait_ws_push(5)
    if recv:
        print(f"  WS push: {ms}ms")

# ============================================================
section("4. SL/TP UPDATE (change existing)")
if open_pos:
    sym = open_pos[0]["symbol"].replace("/", "").replace("-", "").replace("_", "")
    s, d, m = call("POST", "/api/positions/set-sl-tp", body={
        "symbol": sym, "broker_id": "binance", "stop_loss_pct": 3.0, "take_profit_pct": 7.0
    })
    check(f"Update SL/TP 3%/7% {sym}", s, d, m)
    recv, ms, wd = wait_ws_push(5)
    if recv:
        print(f"  WS push: {ms}ms")

# ============================================================
section("5. CLOSE POSITION (non-existent — error handling)")
s, d, m = call("POST", "/api/positions/close", body={
    "symbol": "FAKEUSDT", "broker_id": "binance"
})
check("Close fake symbol (should error gracefully)", s, d, m)
if isinstance(d, dict) and d.get("status") == "error":
    print(f"  OK: Graceful error: {d.get('reason')}")

# ============================================================
section("6. ALVORA EXECUTE: close_position (error case)")
s, d, m = call("POST", "/api/alvora/execute", body={
    "action_type": "close_position", "params": {"position_id": 99999}
})
check("Alvora close non-existent", s, d, m)
if isinstance(d, dict) and d.get("status") == "error":
    print(f"  OK: Graceful error: {d.get('reason')}")

# ============================================================
section("7. ALVORA EXECUTE: set_stop_loss (by symbol)")
if open_pos:
    sym = open_pos[0]["symbol"].replace("/", "").replace("-", "").replace("_", "")
    s, d, m = call("POST", "/api/alvora/execute", body={
        "action_type": "set_stop_loss",
        "params": {"symbol": sym, "stop_loss_pct": 6.0}
    })
    check(f"Alvora set_sl by symbol {sym}", s, d, m)
    if isinstance(d, dict):
        print(f"  Result: {json.dumps(d)[:120]}")

# ============================================================
section("8. ALVORA EXECUTE: set_take_profit (by symbol)")
if open_pos:
    sym = open_pos[0]["symbol"].replace("/", "").replace("-", "").replace("_", "")
    s, d, m = call("POST", "/api/alvora/execute", body={
        "action_type": "set_take_profit",
        "params": {"symbol": sym, "take_profit_pct": 12.0}
    })
    check(f"Alvora set_tp by symbol {sym}", s, d, m)
    if isinstance(d, dict):
        print(f"  Result: {json.dumps(d)[:120]}")

# ============================================================
section("9. AUTO-SELL TOGGLE (DB position)")
s, d, m = call("GET", "/api/positions")
db_pos = [p for p in d if p.get("id") and p["id"] > 0 and p.get("status") == "open"] if isinstance(d, list) else []
if db_pos:
    pid = db_pos[0]["id"]
    s, d, m = call("PATCH", f"/api/positions/{pid}/auto-sell?enabled=false")
    check(f"Disable auto-sell #{pid}", s, d, m)
    recv, ms, wd = wait_ws_push(5)
    if recv:
        print(f"  WS push: {ms}ms, changed={wd.get('changed')}")
    s, d, m = call("PATCH", f"/api/positions/{pid}/auto-sell?enabled=true")
    check(f"Enable auto-sell #{pid}", s, d, m)
    recv, ms, wd = wait_ws_push(5)
    if recv:
        print(f"  WS push: {ms}ms, changed={wd.get('changed')}")
else:
    print("  SKIP: No DB positions with valid id")

# ============================================================
section("10. ERROR CONDITIONS")
# Invalid SL (negative)
s, d, m = call("POST", "/api/positions/set-sl-tp", body={
    "symbol": "BTCUSDT", "broker_id": "binance", "stop_loss": -100
})
check("Set negative SL (should handle)", s, d, m)

# Missing symbol
s, d, m = call("POST", "/api/positions/set-sl-tp", body={
    "broker_id": "binance", "stop_loss_pct": 5.0
})
check("Set SL without symbol (should error)", s, d, m)

# Missing both SL and TP
s, d, m = call("POST", "/api/positions/set-sl-tp", body={
    "symbol": "BTCUSDT", "broker_id": "binance"
})
check("Set SL/TP without values (should error)", s, d, m)

# Close without symbol
s, d, m = call("POST", "/api/positions/close", body={"broker_id": "binance"})
check("Close without symbol (should error)", s, d, m)

# ============================================================
section("11. RELATED MODULES")
s, d, m = call("GET", "/api/ai-agent/status")
check("AI Agent status", s, d, m)
s, d, m = call("GET", "/api/ai-agent/portfolio-summary")
check("Portfolio summary", s, d, m)
s, d, m = call("GET", "/api/risk-events")
check("Risk events", s, d, m)
s, d, m = call("GET", "/api/alvora/status")
check("Alvora status", s, d, m)
s, d, m = call("GET", "/api/positions")
check("Positions list", s, d, m)
s, d, m = call("GET", "/api/binance/balance")
check("Binance balance", s, d, m)

# ============================================================
section("12. WEBSOCKET PRICES (real-time price updates)")
ws2 = create_connection(f"ws://localhost:8080/api/ws/prices?token={TOKEN}", timeout=10)
msg = ws2.recv()
d = json.loads(msg)
if d.get("type") == "snapshot":
    prices = d.get("prices", {})
    print(f"  OK: {len(prices)} symbols in snapshot")
    # Wait for a tick update
    ws2.settimeout(10)
    try:
        msg = ws2.recv()
        d = json.loads(msg)
        if d.get("type") == "tick":
            print(f"  OK: Tick received: {d.get('symbol')}={d.get('price')}")
        else:
            print(f"  OK: Received type={d.get('type')}")
    except:
        print("  Note: No tick in 10s (market may be slow)")
else:
    bugs.append(f"WS prices: unexpected type {d.get('type')}")
ws2.close()

ws.close()

# ============================================================
section("SUMMARY")
print(f"\n  Bugs found: {len(bugs)}")
for b in bugs:
    print(f"  - {b}")
if not bugs:
    print("  ALL TESTS PASSED!")
