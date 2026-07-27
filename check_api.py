import requests

base = "http://127.0.0.1:18652"
endpoints = [
    "/health",
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
        r = requests.get(base + e, timeout=5)
        print(f"{e} [{r.status_code}]: {r.text[:500]}")
    except Exception as ex:
        print(f"{e}: ERROR - {ex}")
    print()
