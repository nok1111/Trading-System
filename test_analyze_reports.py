"""Test analyze_positions saves recommendations with correct user_id."""
import httpx
import json
import time

AUTH_URL = "http://76.13.180.80:8000"
API_URL = "http://76.13.180.80:8080"

# Login
r = httpx.post(f"{AUTH_URL}/api/auth/login", json={
    "email": "nokturnog@gmail.com",
    "password": "panicopain1",
}, timeout=10)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# Get user info
r = httpx.get(f"{AUTH_URL}/api/auth/me", headers=headers, timeout=10)
user_id = r.json().get("id")
print(f"User ID: {user_id}")

print("=" * 70)
print("ANALYZE POSITIONS + REPORTS TEST")
print("=" * 70)

# 1. Check current reports
print("\n--- 1. GET /api/intelligence/reports/all (before) ---")
r = httpx.get(f"{API_URL}/api/intelligence/reports/all?limit=50", headers=headers, timeout=10)
data = r.json()
print(f"  Reports count: {len(data)}")
for rep in data[:3]:
    print(f"  - {rep.get('id')} | {rep.get('asset')} | {rep.get('action_type')} | {rep.get('summary', '')[:60]}")

# 2. Save AI config first (groq + model)
print("\n--- 2. POST /api/settings/ai-config (save groq config) ---")
r = httpx.post(f"{API_URL}/api/settings/ai-config", headers=headers, json={
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
}, timeout=10)
print(f"  Status: {r.status_code} | {r.json()}")

# 3. Run analyze-positions with a test position
print("\n--- 3. POST /api/ai-agent/analyze-positions (DOGEUSDT) ---")
r = httpx.post(f"{API_URL}/api/ai-agent/analyze-positions", headers=headers, json={
    "positions": [{
        "id": 1,
        "symbol": "DOGEUSDT",
        "side": "long",
        "quantity": 100,
        "entry_price": 0.15,
        "current_price": 0.16,
        "stop_loss": 0.14,
        "take_profit": 0.18,
        "unrealized_pnl": 1.0,
    }],
    "broker": "paper",
}, timeout=10)
print(f"  Status: {r.status_code}")
print(f"  Response: {r.json()}")

# 4. Wait for analysis to complete
print("\n--- 4. Waiting for analysis to complete (checking logs)... ---")
for i in range(30):
    time.sleep(5)
    r = httpx.get(f"{API_URL}/api/ai-agent/logs?limit=5", headers=headers, timeout=10)
    logs = r.json()
    if isinstance(logs, list):
        last_logs = [l.get("message", "") for l in logs[:5]]
        print(f"  [{i*5}s] Last logs: {last_logs}")
        if any("guardadas en Reportes" in m for m in last_logs):
            print("  ✓ Analysis completed!")
            break
        if any("Error" in m or "no respondió" in m for m in last_logs):
            print(f"  ✗ Error detected: {last_logs}")
            break
    else:
        print(f"  [{i*5}s] Logs response: {str(logs)[:200]}")

# 5. Check reports after analysis
print("\n--- 5. GET /api/intelligence/reports/all (after) ---")
r = httpx.get(f"{API_URL}/api/intelligence/reports/all?limit=50", headers=headers, timeout=10)
data = r.json()
print(f"  Reports count: {len(data)}")
for rep in data[:5]:
    print(f"  - {rep.get('id')} | {rep.get('asset')} | {rep.get('action_type')} | {rep.get('summary', '')[:80]}")

# 6. Check reports for DOGE specifically
print("\n--- 6. GET /api/intelligence/reports/DOGE ---")
r = httpx.get(f"{API_URL}/api/intelligence/reports/DOGE?limit=20", headers=headers, timeout=10)
data = r.json()
print(f"  DOGE reports count: {len(data)}")
for rep in data[:5]:
    print(f"  - {rep.get('id')} | {rep.get('action_type')} | {rep.get('summary', '')[:80]}")
    if rep.get("metadata"):
        print(f"    metadata: {json.dumps(rep['metadata'], default=str)[:200]}")

print(f"\n{'=' * 70}")
print("TEST COMPLETE")
print(f"{'=' * 70}")
