"""Test position close, SL/TP, auto-sell endpoints + real-time behavior."""
import time, json, requests, threading

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
if s == 200 and isinstance(d, list):
    open_pos = [p for p in d if p.get("status") == "open"]
    closed_pos = [p for p in d if p.get("status") == "closed"]
    print(f"  Open: {len(open_pos)}, Closed: {len(closed_pos)}")
    for p in open_pos[:5]:
        print(f"    #{p.get('id')} {p.get('symbol')} side={p.get('side')} qty={p.get('quantity')} SL={p.get('stop_loss')} TP={p.get('take_profit')} auto_sell={p.get('auto_sell_enabled')} broker={p.get('broker_id')}")

# ============================================================
# 2. Test auto-sell toggle
# ============================================================
section("2. AUTO-SELL TOGGLE")
if open_pos:
    test_pos = open_pos[0]
    pid = test_pos.get("id")
    if pid and pid > 0:
        # Disable auto-sell
        s, d, m = call("PATCH", f"/api/positions/{pid}/auto-sell?enabled=false")
        check(f"Disable auto-sell #{pid}", s, d, m)
        if s == 200:
            print(f"    Result: {d}")
        # Re-enable auto-sell
        s, d, m = call("PATCH", f"/api/positions/{pid}/auto-sell?enabled=true")
        check(f"Enable auto-sell #{pid}", s, d, m)
        if s == 200:
            print(f"    Result: {d}")
    else:
        print(f"  SKIP: Position has id={pid} (broker-managed, no DB id)")

# ============================================================
# 3. Test SL/TP via Alvora execute
# ============================================================
section("3. SL/TP VIA ALVORA EXECUTE")
if open_pos:
    test_pos = None
    for p in open_pos:
        if p.get("id") and p["id"] > 0:
            test_pos = p
            break
    if test_pos:
        pid = test_pos["id"]
        sym = test_pos["symbol"]
        entry = float(test_pos.get("entry_price") or 0)
        if entry > 0:
            sl_abs = round(entry * 0.95, 2)  # 5% below entry
            tp_abs = round(entry * 1.10, 2)  # 10% above entry
            print(f"  Test pos: #{pid} {sym} entry={entry} SL={sl_abs} TP={tp_abs}")
            
            # Set SL via Alvora execute
            s, d, m = call("POST", "/api/alvora/execute", body={
                "action_type": "set_stop_loss",
                "params": {"position_id": pid, "symbol": sym, "stop_loss": sl_abs}
            })
            check(f"Set SL #{pid}", s, d, m)
            if isinstance(d, dict):
                print(f"    Result: {json.dumps(d)[:150]}")
            
            # Set TP via Alvora execute
            s, d, m = call("POST", "/api/alvora/execute", body={
                "action_type": "set_take_profit",
                "params": {"position_id": pid, "symbol": sym, "take_profit": tp_abs}
            })
            check(f"Set TP #{pid}", s, d, m)
            if isinstance(d, dict):
                print(f"    Result: {json.dumps(d)[:150]}")
            
            # Verify SL/TP was set
            s, d, m = call("GET", "/api/positions")
            if s == 200:
                updated = next((p for p in d if p.get("id") == pid), None)
                if updated:
                    print(f"  Verify: SL={updated.get('stop_loss')} TP={updated.get('take_profit')}")
                    if float(updated.get("stop_loss") or 0) != sl_abs:
                        bugs.append(f"SL not persisted: expected {sl_abs}, got {updated.get('stop_loss')}")
                    if float(updated.get("take_profit") or 0) != tp_abs:
                        bugs.append(f"TP not persisted: expected {tp_abs}, got {updated.get('take_profit')}")
    else:
        print("  SKIP: No DB positions with valid id")

# ============================================================
# 4. Test SL/TP via percentage
# ============================================================
section("4. SL/TP VIA PERCENTAGE")
if open_pos:
    test_pos = None
    for p in open_pos:
        if p.get("id") and p["id"] > 0:
            test_pos = p
            break
    if test_pos:
        pid = test_pos["id"]
        sym = test_pos["symbol"]
        entry = float(test_pos.get("entry_price") or 0)
        if entry > 0:
            expected_sl = round(entry * 0.97, 2)  # 3% below
            expected_tp = round(entry * 1.08, 2)  # 8% above
            print(f"  Test pos: #{pid} {sym} entry={entry}")
            print(f"  Expected: SL={expected_sl} (3%) TP={expected_tp} (8%)")
            
            s, d, m = call("POST", "/api/alvora/execute", body={
                "action_type": "set_stop_loss",
                "params": {"position_id": pid, "symbol": sym, "stop_loss_pct": 3.0}
            })
            check(f"Set SL 3% #{pid}", s, d, m)
            if isinstance(d, dict):
                print(f"    Result: {json.dumps(d)[:150]}")
            
            s, d, m = call("POST", "/api/alvora/execute", body={
                "action_type": "set_take_profit",
                "params": {"position_id": pid, "symbol": sym, "take_profit_pct": 8.0}
            })
            check(f"Set TP 8% #{pid}", s, d, m)
            if isinstance(d, dict):
                print(f"    Result: {json.dumps(d)[:150]}")
            
            # Verify
            s, d, m = call("GET", "/api/positions")
            if s == 200:
                updated = next((p for p in d if p.get("id") == pid), None)
                if updated:
                    actual_sl = float(updated.get("stop_loss") or 0)
                    actual_tp = float(updated.get("take_profit") or 0)
                    print(f"  Verify: SL={actual_sl} TP={actual_tp}")
                    if abs(actual_sl - expected_sl) > 0.01:
                        bugs.append(f"SL pct mismatch: expected {expected_sl}, got {actual_sl}")
                    if abs(actual_tp - expected_tp) > 0.01:
                        bugs.append(f"TP pct mismatch: expected {expected_tp}, got {actual_tp}")

# ============================================================
# 5. Test close position via Alvora execute
# ============================================================
section("5. CLOSE POSITION VIA ALVORA EXECUTE")
# We need a position we can safely close. Let's check if there's a small one.
if open_pos:
    # Find a DB position with valid id
    closeable = [p for p in open_pos if p.get("id") and p["id"] > 0]
    if closeable:
        # Don't actually close — just test the endpoint with a non-existent position
        s, d, m = call("POST", "/api/alvora/execute", body={
            "action_type": "close_position",
            "params": {"position_id": 99999}
        })
        check(f"Close non-existent pos (should error)", s, d, m, exp=200)
        if isinstance(d, dict):
            print(f"    Result: {json.dumps(d)[:150]}")
            if d.get("status") == "error":
                print("    OK: Correctly returned error for non-existent position")
            else:
                bugs.append("Close non-existent pos should return error status")
    else:
        print("  SKIP: No closeable DB positions")

# ============================================================
# 6. Test paper trading sell (the endpoint the frontend actually calls)
# ============================================================
section("6. PAPER TRADING SELL (frontend Sell button endpoint)")
s, d, m = call("POST", "/api/paper-trading/sell", body={"symbol": "BTCUSDT"})
check("Paper sell BTCUSDT", s, d, m)
if isinstance(d, dict):
    print(f"    Result: {json.dumps(d)[:150]}")

# ============================================================
# 7. Test WebSocket positions endpoint
# ============================================================
section("7. WEBSOCKET POSITIONS ENDPOINT")
try:
    from websocket import create_connection
    ws_url = f"ws://localhost:8080/api/ws/positions/binance?token={TOKEN}"
    print(f"  Connecting to {ws_url[:60]}...")
    ws = create_connection(ws_url, timeout=10)
    msg = ws.recv()
    print(f"  Received: {msg[:200]}")
    d = json.loads(msg)
    if d.get("type") in ("snapshot", "update", "error"):
        print(f"  OK: WS positions type={d.get('type')}, positions={len(d.get('positions',[]))}")
    else:
        bugs.append(f"WS positions: unexpected message type {d.get('type')}")
    ws.close()
except ImportError:
    print("  SKIP: websocket-client not installed")
except Exception as e:
    print(f"  FAIL: WS positions error: {e}")
    bugs.append(f"WS positions: {e}")

# ============================================================
# 8. Test WebSocket prices endpoint
# ============================================================
section("8. WEBSOCKET PRICES ENDPOINT")
try:
    from websocket import create_connection
    ws_url = f"ws://localhost:8080/api/ws/prices?token={TOKEN}"
    print(f"  Connecting to {ws_url[:60]}...")
    ws = create_connection(ws_url, timeout=10)
    msg = ws.recv()
    print(f"  Received: {msg[:200]}")
    d = json.loads(msg)
    if d.get("type") == "snapshot":
        prices = d.get("prices", {})
        print(f"  OK: WS prices snapshot with {len(prices)} symbols")
    else:
        bugs.append(f"WS prices: unexpected message type {d.get('type')}")
    ws.close()
except ImportError:
    print("  SKIP: websocket-client not installed")
except Exception as e:
    print(f"  FAIL: WS prices error: {e}")
    bugs.append(f"WS prices: {e}")

# ============================================================
# SUMMARY
# ============================================================
section("SUMMARY")
print(f"\n  Bugs found: {len(bugs)}")
for b in bugs:
    print(f"  - {b}")
if not bugs:
    print("  ALL TESTS PASSED!")
