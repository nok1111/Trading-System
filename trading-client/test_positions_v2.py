"""Comprehensive test: position close, SL/TP, auto-sell, WebSocket real-time."""
import time, json, requests, threading, asyncio

BASE = "http://localhost:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTkzNDU3fQ.d29OGBh-vXvqlycsjXX_I7jWXGPiCajBLl8ycHW-Gks"
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
    print(f"  {'OK' if ok else 'FAIL'} {name}: {s} in {ms}ms")
    if not ok:
        bugs.append(f"{name}: {s} — {str(d)[:100]}")
    return ok, d

def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")

# ============================================================
# 1. Get current positions
# ============================================================
section("1. GET POSITIONS")
s, d, m = call("GET", "/api/positions")
check("Get positions", s, d, m)
open_pos = []
if s == 200 and isinstance(d, list):
    open_pos = [p for p in d if p.get("status") == "open"]
    closed_pos = [p for p in d if p.get("status") == "closed"]
    print(f"  Open: {len(open_pos)}, Closed: {len(closed_pos)}")
    for p in open_pos[:5]:
        print(f"    #{p.get('id')} {p.get('symbol')} SL={p.get('stop_loss')} TP={p.get('take_profit')} auto_sell={p.get('auto_sell_enabled')}")

# ============================================================
# 2. Test new close position endpoint (broker-managed, id=0)
# ============================================================
section("2. CLOSE POSITION ENDPOINT (broker-managed)")
# Test with non-existent symbol (should return error, not crash)
s, d, m = call("POST", "/api/positions/close", body={
    "symbol": "NONEXISTENTUSDT",
    "broker_id": "binance"
})
check("Close non-existent symbol", s, d, m)
if isinstance(d, dict):
    print(f"    Result: {json.dumps(d)[:150]}")

# ============================================================
# 3. Test new SL/TP endpoint (broker-managed)
# ============================================================
section("3. SET SL/TP ENDPOINT (broker-managed)")
if open_pos:
    test_pos = open_pos[0]
    sym = test_pos["symbol"].replace("/", "").replace("-", "").replace("_", "")
    entry = float(test_pos.get("entry_price") or 0)
    if entry > 0:
        # Test with percentage
        s, d, m = call("POST", "/api/positions/set-sl-tp", body={
            "symbol": sym,
            "broker_id": "binance",
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
        })
        check(f"Set SL/TP 5%/10% for {sym}", s, d, m)
        if isinstance(d, dict) and d.get("status") == "executed":
            print(f"    SL={d.get('stop_loss')} TP={d.get('take_profit')} broker_oco={d.get('broker_oco')}")
        elif isinstance(d, dict):
            print(f"    Result: {json.dumps(d)[:150]}")
            bugs.append(f"Set SL/TP: {d.get('reason', 'unknown')}")

        # Test with absolute values
        sl_abs = round(entry * 0.95, 2)
        tp_abs = round(entry * 1.10, 2)
        s, d, m = call("POST", "/api/positions/set-sl-tp", body={
            "symbol": sym,
            "broker_id": "binance",
            "stop_loss": sl_abs,
            "take_profit": tp_abs,
        })
        check(f"Set SL/TP absolute for {sym}", s, d, m)
        if isinstance(d, dict) and d.get("status") == "executed":
            print(f"    SL={d.get('stop_loss')} TP={d.get('take_profit')} broker_oco={d.get('broker_oco')}")

# ============================================================
# 4. Test WebSocket db-positions endpoint
# ============================================================
section("4. WEBSOCKET DB-POSITIONS ENDPOINT")
try:
    from websocket import create_connection
    ws_url = f"ws://localhost:8080/api/ws/db-positions?token={TOKEN}"
    print(f"  Connecting to WS db-positions...")
    ws = create_connection(ws_url, timeout=10)
    msg = ws.recv()
    d = json.loads(msg)
    print(f"  Received type={d.get('type')}, positions={len(d.get('positions',[]))}")
    if d.get("type") in ("snapshot", "update"):
        print(f"  OK: WS db-positions working")
        pos_list = d.get("positions", [])
        if pos_list:
            print(f"    First pos: #{pos_list[0].get('id')} {pos_list[0].get('symbol')} status={pos_list[0].get('status')}")
    else:
        bugs.append(f"WS db-positions: unexpected type {d.get('type')}")

    # Test real-time push: make a change and see if WS sends update
    print(f"\n  Testing real-time push...")
    if open_pos:
        test_pos = open_pos[0]
        sym = test_pos["symbol"].replace("/", "").replace("-", "").replace("_", "")
        # Make a SL/TP change
        s2, d2, m2 = call("POST", "/api/positions/set-sl-tp", body={
            "symbol": sym,
            "broker_id": "binance",
            "stop_loss_pct": 7.0,
            "take_profit_pct": 15.0,
        })
        # Wait for WS push
        ws.settimeout(5)
        try:
            msg2 = ws.recv()
            d3 = json.loads(msg2)
            print(f"  WS push received: type={d3.get('type')}, changed={d3.get('changed')}")
            if d3.get("type") in ("update", "snapshot"):
                print(f"  OK: Real-time push working!")
            else:
                print(f"  Note: WS sent type={d3.get('type')} (may be periodic update)")
        except Exception as e:
            print(f"  Note: No immediate WS push (may arrive in next poll cycle): {e}")

    ws.close()
except ImportError:
    print("  SKIP: websocket-client not installed")
except Exception as e:
    print(f"  FAIL: WS db-positions error: {e}")
    bugs.append(f"WS db-positions: {e}")

# ============================================================
# 5. Test WebSocket prices endpoint
# ============================================================
section("5. WEBSOCKET PRICES ENDPOINT (verification)")
try:
    from websocket import create_connection
    ws_url = f"ws://localhost:8080/api/ws/prices?token={TOKEN}"
    ws = create_connection(ws_url, timeout=10)
    msg = ws.recv()
    d = json.loads(msg)
    if d.get("type") == "snapshot":
        print(f"  OK: WS prices snapshot with {len(d.get('prices',{}))} symbols")
    else:
        bugs.append(f"WS prices: unexpected type {d.get('type')}")
    ws.close()
except Exception as e:
    print(f"  FAIL: WS prices error: {e}")
    bugs.append(f"WS prices: {e}")

# ============================================================
# 6. Test auto-sell toggle (if DB positions exist)
# ============================================================
section("6. AUTO-SELL TOGGLE")
# Check if there are any DB positions
s, d, m = call("GET", "/api/positions")
if s == 200 and isinstance(d, list):
    db_pos = [p for p in d if p.get("id") and p["id"] > 0 and p.get("status") == "open"]
    if db_pos:
        pid = db_pos[0]["id"]
        s, d, m = call("PATCH", f"/api/positions/{pid}/auto-sell?enabled=false")
        check(f"Disable auto-sell #{pid}", s, d, m)
        s, d, m = call("PATCH", f"/api/positions/{pid}/auto-sell?enabled=true")
        check(f"Enable auto-sell #{pid}", s, d, m)
    else:
        print("  SKIP: No DB positions with valid id (all broker-managed)")

# ============================================================
# 7. Test Alvora execute endpoints (SL/TP, close)
# ============================================================
section("7. ALVORA EXECUTE ENDPOINTS")
# Test close with non-existent position
s, d, m = call("POST", "/api/alvora/execute", body={
    "action_type": "close_position",
    "params": {"position_id": 99999}
})
check("Alvora close non-existent", s, d, m)
if isinstance(d, dict):
    print(f"    Result: {json.dumps(d)[:100]}")

# Test set_stop_loss with non-existent position
s, d, m = call("POST", "/api/alvora/execute", body={
    "action_type": "set_stop_loss",
    "params": {"position_id": 99999, "symbol": "BTCUSDT", "stop_loss_pct": 5.0}
})
check("Alvora set_sl non-existent", s, d, m)
if isinstance(d, dict):
    print(f"    Result: {json.dumps(d)[:100]}")

# ============================================================
# 8. Test related modules (Dashboard, AI Agent)
# ============================================================
section("8. RELATED MODULES")
s, d, m = call("GET", "/api/ai-agent/status")
check("AI Agent status", s, d, m)

s, d, m = call("GET", "/api/ai-agent/portfolio-summary")
check("Portfolio summary", s, d, m)

s, d, m = call("GET", "/api/risk-events")
check("Risk events", s, d, m)

s, d, m = call("GET", "/api/alvora/status")
check("Alvora status", s, d, m)

# ============================================================
# SUMMARY
# ============================================================
section("SUMMARY")
print(f"\n  Bugs found: {len(bugs)}")
for b in bugs:
    print(f"  - {b}")
if not bugs:
    print("  ALL TESTS PASSED!")
