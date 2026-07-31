import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")

# Read .env to get AUTH_SERVER_URL
env_vars = {}
env_path = "/opt/trading-system/.env"
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")

print(f"AUTH_SERVER_URL from .env: {env_vars.get('AUTH_SERVER_URL', 'NOT FOUND')}")
print(f"ENCRYPTION_KEY from .env: {env_vars.get('ENCRYPTION_KEY', 'NOT FOUND')}")

# Set env vars
for k, v in env_vars.items():
    os.environ.setdefault(k, v)

# Now try decrypt
from app.database.session import SessionLocal
from sqlalchemy import text
from app.services.crypto import decrypt

db = SessionLocal()
result = db.execute(text("SELECT api_key_enc, api_secret_enc FROM broker_accounts WHERE broker_id='binance' AND status='CONNECTED_TRADING' ORDER BY created_at LIMIT 1"))
row = result.fetchone()
if row:
    try:
        api_key = decrypt(row[0])
        api_secret = decrypt(row[1])
        print(f"Decrypted OK: api_key len={len(api_key)}, api_secret len={len(api_secret)}")
        
        def signed_get(base_url, path, params=None):
            params = params or {}
            params["timestamp"] = int(time.time() * 1000)
            query = urllib.parse.urlencode(params)
            sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            url = f"{base_url}{path}?{query}&signature={sig}"
            r = httpx.get(url, headers={"X-MBX-APIKEY": api_key}, timeout=10)
            return r.json()
        
        # Check futures
        try:
            fapi = signed_get("https://fapi.binance.com", "/fapi/v2/positionRisk")
            if isinstance(fapi, list):
                doge_f = [p for p in fapi if "DOGE" in p.get("symbol", "") and float(p.get("positionAmt", 0)) != 0]
                if doge_f:
                    for p in doge_f:
                        print(f"FUTURES: symbol={p['symbol']} qty={p['positionAmt']} entry={p['entryPrice']} mark={p['markPrice']}")
                else:
                    print("No DOGE futures positions on Binance")
            else:
                print(f"Futures response (not list): {str(fapi)[:200]}")
        except Exception as e:
            print(f"Futures check error: {e}")
        
        # Check spot
        try:
            account = signed_get("https://api.binance.com", "/api/v3/account")
            if "balances" in account:
                doge = [b for b in account["balances"] if b["asset"] == "DOGE" and (float(b["free"]) > 0 or float(b["locked"]) > 0)]
                if doge:
                    for b in doge:
                        print(f"SPOT: asset={b['asset']} free={b['free']} locked={b['locked']}")
                else:
                    print("No DOGE spot balance on Binance")
            else:
                print(f"Spot response (no balances): {str(account)[:200]}")
        except Exception as e:
            print(f"Spot check error: {e}")
    except Exception as e:
        print(f"Decrypt error: {type(e).__name__}: {e}")

db.close()
