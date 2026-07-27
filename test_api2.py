import requests

# Login to Auth Server
auth_url = "http://76.13.180.80:8000"
login_resp = requests.post(f"{auth_url}/api/auth/login", json={
    "email": "nokturnog@gmail.com",
    "password": "panicopain1"
})
print(f"Login: {login_resp.status_code}")
token = login_resp.json().get("token")

base = "http://127.0.0.1:18652"
headers = {"Authorization": f"Bearer {token}"}

# Check snapshots
r = requests.get(f"{base}/api/snapshots", headers=headers, timeout=15)
print(f"\nSnapshots [{r.status_code}]: {r.text[:500]}")

# Check trading-mode (for allocated_capital)
r = requests.get(f"{base}/api/ai-agent/trading-mode", headers=headers, timeout=15)
print(f"\nTrading-mode [{r.status_code}]: {r.text[:500]}")

# Check stats
r = requests.get(f"{base}/api/stats", headers=headers, timeout=15)
print(f"\nStats [{r.status_code}]: {r.text[:500]}")

# Check binance balance
r = requests.get(f"{base}/api/binance/balance", headers=headers, timeout=15)
print(f"\nBinance balance [{r.status_code}]: {r.text[:500]}")

# Check positions
r = requests.get(f"{base}/api/positions", headers=headers, timeout=15)
print(f"\nPositions [{r.status_code}]: {r.text[:500]}")
