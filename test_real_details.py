"""Check positions and their user_id, SL/TP data for real user."""
import httpx
import json

VPS = "http://76.13.180.80"
BACKEND = f"{VPS}:8080"
AUTH = f"{VPS}:8000"

r = httpx.post(f"{AUTH}/api/auth/login", json={"email": "nokturnog@gmail.com", "password": "panicopain1"}, timeout=10)
jwt = r.json().get("token")
h = {"Authorization": f"Bearer {jwt}"}

# Get positions
r = httpx.get(f"{BACKEND}/api/positions", headers=h, timeout=15)
positions = r.json()
print(f"Positions: {len(positions)}")
for p in positions:
    print(f"  ID={p.get('id')} symbol={p.get('symbol')} status={p.get('status')} side={p.get('side')}")
    print(f"    entry={p.get('entry_price')} qty={p.get('quantity')} current={p.get('current_price')}")
    print(f"    stop_loss={p.get('stop_loss')} take_profit={p.get('take_profit')}")
    print(f"    strategy={p.get('strategy_name')} pnl={p.get('unrealized_pnl')}")
    meta = p.get('metadata_json') or {}
    if meta:
        print(f"    metadata: {json.dumps(meta, default=str)[:200]}")
    print()

# Check AIRecommendation table
print("="*80)
print("Checking AIRecommendation table directly...")
r = httpx.get(f"{BACKEND}/api/intelligence/reports/all", headers=h, timeout=15)
print(f"reports/all: {len(r.json())} items")

# Check alerts endpoint in detail
print("\n" + "="*80)
print("Checking alerts...")
r = httpx.get(f"{BACKEND}/api/intelligence/alerts?limit=20", headers=h, timeout=15)
print(f"alerts: {len(r.json())} items")

# Check price-alerts
r = httpx.get(f"{BACKEND}/api/intelligence/price-alerts", headers=h, timeout=15)
print(f"price-alerts: {len(r.json())} items")

# Check the Position model to see if user_id exists
print("\n" + "="*80)
print("Checking Position model fields...")
