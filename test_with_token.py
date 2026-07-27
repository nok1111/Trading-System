import requests

# Login to Auth Server
auth_url = "http://76.13.180.80:8000"
login_resp = requests.post(f"{auth_url}/api/auth/login", json={
    "email": "nokturnog@gmail.com",
    "password": "panicopain1"
})
print(f"Login status: {login_resp.status_code}")
print(f"Login response: {login_resp.text[:300]}")

if login_resp.status_code == 200:
    token = login_resp.json().get("token")
    print(f"\nToken: {token[:50]}...")

    # Test trading-client endpoints with token
    base = "http://127.0.0.1:18652"
    headers = {"Authorization": f"Bearer {token}"}
    endpoints = [
        "/api/stats",
        "/api/binance/balance",
        "/api/snapshots",
        "/api/positions",
        "/api/ai-agent/capital",
        "/api/signals",
        "/api/ai-agent/log",
    ]

    for e in endpoints:
        try:
            r = requests.get(base + e, headers=headers, timeout=15)
            print(f"\n{e} [{r.status_code}]: {r.text[:300]}")
        except Exception as ex:
            print(f"\n{e}: ERROR - {ex}")
