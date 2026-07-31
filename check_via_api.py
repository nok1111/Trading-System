import httpx
import time
import hmac
import hashlib
import urllib.parse

# Use the running API to check Binance positions
# First, get a valid token by logging in
BASE = "http://localhost:8080"

# Try to login
try:
    resp = httpx.post(f"{BASE}/api/auth/login", json={"username": "nokturno", "password": "nokturno"}, timeout=10)
    print(f"Login: {resp.status_code}")
    if resp.status_code == 200:
        token = resp.json().get("access_token")
        print(f"Token: {token[:20]}...")
    else:
        print(f"Login response: {resp.text[:200]}")
        # Try other endpoints
        resp = httpx.post(f"{BASE}/api/auth/login", json={"email": "nokturno", "password": "nokturno"}, timeout=10)
        print(f"Login2: {resp.status_code} {resp.text[:200]}")
except Exception as e:
    print(f"Login error: {e}")

# Try to import positions via the API
try:
    # Get token from auth server
    auth_resp = httpx.post("http://localhost:8000/api/auth/login", json={"username": "nokturno", "password": "nokturno"}, timeout=10)
    print(f"Auth login: {auth_resp.status_code}")
    if auth_resp.status_code == 200:
        token = auth_resp.json().get("access_token")
        print(f"Auth token: {token[:20]}...")
        
        # Import positions
        resp = httpx.post(f"{BASE}/api/ai-agent/binance/import-positions", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        print(f"Import: {resp.status_code}")
        print(f"Import response: {resp.text[:500]}")
    else:
        print(f"Auth login response: {auth_resp.text[:200]}")
except Exception as e:
    print(f"Import error: {e}")
