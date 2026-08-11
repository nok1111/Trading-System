import requests
import json

results = []

# Login first
r = requests.post("http://76.13.180.80:8000/api/auth/login",
                  json={"email": "test@alvora.dev", "password": "test123456"},
                  timeout=10)
token = r.json().get("token")
results.append(f"Token: {token[:30]}...")

# Create with invalid creds
r = requests.post("http://76.13.180.80:8080/api/broker-accounts",
                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                  json={"brokerId": "binance", "apiKey": "xxx", "apiSecret": "yyy", "environment": "testnet"},
                  timeout=15)
results.append(f"\nPOST create (invalid creds): {r.status_code}")
results.append(f"Response: {r.text[:400]}")

# GET accounts
r = requests.get("http://76.13.180.80:8080/api/broker-accounts",
                 headers={"Authorization": f"Bearer {token}"},
                 timeout=10)
results.append(f"\nGET accounts: {r.status_code}")
results.append(f"Response: {r.text[:200]}")

# Through Vite proxy
try:
    r = requests.get("http://localhost:1420/api/broker-accounts",
                     headers={"Authorization": f"Bearer {token}"},
                     timeout=10)
    results.append(f"\nProxy GET: {r.status_code}")
    results.append(f"Response: {r.text[:200]}")
except Exception as e:
    results.append(f"\nProxy error: {e}")

# Validate through proxy
try:
    r = requests.post("http://localhost:1420/api/broker-accounts/validate",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      json={"brokerId": "binance", "apiKey": "xxx", "apiSecret": "yyy", "environment": "testnet"},
                      timeout=15)
    results.append(f"\nProxy validate: {r.status_code}")
    results.append(f"Response: {r.text[:300]}")
except Exception as e:
    results.append(f"\nProxy validate error: {e}")

with open("_test_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print("Results written to _test_results.txt")
