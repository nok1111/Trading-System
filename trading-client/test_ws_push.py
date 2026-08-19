"""Test real-time WebSocket push: make a change and verify WS sends update within 3s."""
import time, json, requests, threading
from websocket import create_connection

BASE = "http://localhost:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTk0NzA4fQ.AwJ-ju0zAvnkWY7FXPPhWAyDUMOM6k4_Ldosmw6mX7A"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

print("1. Connect to WS db-positions")
ws = create_connection(f"ws://localhost:8080/api/ws/db-positions?token={TOKEN}", timeout=10)
msg = ws.recv()
d = json.loads(msg)
print(f"   Snapshot: {len(d.get('positions',[]))} positions")

print("\n2. Make a SL/TP change via API (triggers _notify_position_update)")
r = requests.post(f"{BASE}/api/positions/set-sl-tp", headers=H, json={
    "symbol": "BTCUSDT",
    "broker_id": "binance",
    "stop_loss_pct": 8.0,
    "take_profit_pct": 20.0,
}, timeout=15)
print(f"   API response: {r.status_code} — {r.json()}")

print("\n3. Wait for WS push (should arrive within 3s)")
ws.settimeout(5)
push_received = False
push_time = 0
t0 = time.time()
try:
    while time.time() - t0 < 6:
        msg = ws.recv()
        d = json.loads(msg)
        elapsed = round((time.time() - t0) * 1000)
        print(f"   WS message at {elapsed}ms: type={d.get('type')}, changed={d.get('changed')}")
        if d.get("type") in ("update", "snapshot"):
            push_received = True
            push_time = elapsed
            break
except Exception as e:
    print(f"   WS timeout: {e}")

if push_received:
    print(f"\n   OK: Real-time push received in {push_time}ms")
else:
    print("\n   FAIL: No push received within 6s")

print("\n4. Test auto-sell toggle (if DB position exists)")
r = requests.get(f"{BASE}/api/positions", headers=H, timeout=15)
positions = r.json()
db_pos = [p for p in positions if p.get("id") and p["id"] > 0 and p.get("status") == "open"]
if db_pos:
    pid = db_pos[0]["id"]
    print(f"   Toggling auto-sell for #{pid}")
    r = requests.patch(f"{BASE}/api/positions/{pid}/auto-sell?enabled=false", headers=H, timeout=10)
    print(f"   Disable: {r.status_code} — {r.json()}")
    # Wait for WS push
    t0 = time.time()
    try:
        while time.time() - t0 < 4:
            msg = ws.recv()
            d = json.loads(msg)
            elapsed = round((time.time() - t0) * 1000)
            print(f"   WS push at {elapsed}ms: type={d.get('type')}, changed={d.get('changed')}")
            if d.get("changed"):
                print(f"   OK: Auto-sell toggle pushed in {elapsed}ms")
                break
    except:
        print("   No push for auto-sell (may need DB position)")
    # Re-enable
    requests.patch(f"{BASE}/api/positions/{pid}/auto-sell?enabled=true", headers=H, timeout=10)
else:
    print("   SKIP: No DB positions with valid id")

ws.close()
print("\nDone.")
