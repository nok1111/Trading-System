import requests, json
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTc5OTQzfQ.yki9p5i282WuQyPyZOGEp5ZkPwh1Py5CXBUcPqoRb3k"
H = {"Authorization": f"Bearer {TOKEN}"}
r = requests.get("http://localhost:8080/api/brokers", headers=H)
brokers = r.json()
print(f"Total brokers: {len(brokers)}")
for b in brokers:
    print(f"  {b['brokerId']}: implemented={b['implemented']}, markets={b['supportedMarkets']}")

# Check connected accounts
r2 = requests.get("http://localhost:8080/api/broker-accounts", headers=H)
accounts = r2.json()
print(f"\nConnected accounts: {len(accounts)}")
for a in accounts:
    print(f"  {a.get('broker_id')}: status={a.get('status')}, env={a.get('environment')}")
