import requests
import json

# Step 1: Register a test user
print("=" * 60)
print("STEP 1: Register test user")
print("=" * 60)
try:
    r = requests.post("http://76.13.180.80:8000/api/auth/register",
                      json={"email": "test@alvora.dev", "username": "testdev", "password": "test123456"},
                      timeout=10)
    print(f"Register: {r.status_code}")
    print(f"Response: {r.text[:200]}")
    if r.status_code == 200 or r.status_code == 201:
        data = r.json()
        token = data.get("token")
        print(f"Token: {token[:30]}..." if token else "No token!")
    elif "already" in r.text.lower() or "exists" in r.text.lower():
        print("User already exists, trying login...")
        r = requests.post("http://76.13.180.80:8000/api/auth/login",
                          json={"email": "test@alvora.dev", "password": "test123456"},
                          timeout=10)
        print(f"Login: {r.status_code}")
        print(f"Response: {r.text[:200]}")
        if r.status_code == 200:
            data = r.json()
            token = data.get("token")
            print(f"Token: {token[:30]}..." if token else "No token!")
        else:
            token = None
    else:
        token = None
except Exception as e:
    print(f"Error: {e}")
    token = None

if not token:
    print("\nFailed to get token, trying login directly...")
    try:
        r = requests.post("http://76.13.180.80:8000/api/auth/login",
                          json={"email": "test@alvora.dev", "password": "test123456"},
                          timeout=10)
        print(f"Login: {r.status_code}")
        print(f"Response: {r.text[:200]}")
        if r.status_code == 200:
            data = r.json()
            token = data.get("token")
            print(f"Token: {token[:30]}..." if token else "No token!")
    except Exception as e:
        print(f"Error: {e}")
        token = None

if not token:
    print("FATAL: Could not get a token. Exiting.")
    exit(1)

# Step 2: Validate license (what the trading-client does)
print("\n" + "=" * 60)
print("STEP 2: Validate license (trading-client -> auth-server)")
print("=" * 60)
try:
    r = requests.post("http://76.13.180.80:8000/api/license/validate",
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=10)
    print(f"License validate: {r.status_code}")
    print(f"Response: {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Step 3: Call broker-accounts through the trading-client (like the frontend does)
print("\n" + "=" * 60)
print("STEP 3: GET /api/broker-accounts (with token)")
print("=" * 60)
try:
    r = requests.get("http://76.13.180.80:8080/api/broker-accounts",
                     headers={"Authorization": f"Bearer {token}"},
                     timeout=10)
    print(f"Broker accounts: {r.status_code}")
    print(f"Response: {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Step 4: Call broker-accounts without token (should 401)
print("\n" + "=" * 60)
print("STEP 4: GET /api/broker-accounts (without token)")
print("=" * 60)
try:
    r = requests.get("http://76.13.180.80:8080/api/broker-accounts",
                     timeout=10)
    print(f"Broker accounts (no token): {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Step 5: Validate broker credentials
print("\n" + "=" * 60)
print("STEP 5: POST /api/broker-accounts/validate (with token)")
print("=" * 60)
try:
    r = requests.post("http://76.13.180.80:8080/api/broker-accounts/validate",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      json={"brokerId": "binance", "apiKey": "test", "apiSecret": "test", "environment": "testnet"},
                      timeout=15)
    print(f"Validate: {r.status_code}")
    print(f"Response: {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Step 6: Check /api/brokers (public endpoint)
print("\n" + "=" * 60)
print("STEP 6: GET /api/brokers (public, no token)")
print("=" * 60)
try:
    r = requests.get("http://76.13.180.80:8080/api/brokers",
                     timeout=10)
    print(f"Brokers: {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
