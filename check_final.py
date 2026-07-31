import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")
from app.database.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Get the encryption key from the running service
# Check .env file
env_path = "/opt/trading-system/.env"
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "ENCRYPTION" in line.upper() or "SECRET_KEY" in line.upper() or "FERNET" in line.upper():
                print(f"ENV: {line.strip()}")

# Also check the settings
from app.config import get_settings
settings = get_settings()
enc_key = getattr(settings, "ENCRYPTION_KEY", None) or getattr(settings, "SECRET_KEY", None)
print(f"Settings ENCRYPTION_KEY: {bool(enc_key)}")
if enc_key:
    print(f"Key prefix: {enc_key[:10]}...")

# Try to decrypt
from app.services.crypto import decrypt, _get_fernet
try:
    f = _get_fernet()
    print(f"Fernet instance: {f}")
except Exception as e:
    print(f"Fernet init error: {e}")

# Get broker account
result = db.execute(text("SELECT api_key_enc, api_secret_enc FROM broker_accounts WHERE broker_id='binance' AND status='CONNECTED_TRADING' ORDER BY created_at LIMIT 1"))
row = result.fetchone()
if row:
    try:
        api_key = decrypt(row[0])
        api_secret = decrypt(row[1])
        print(f"Decrypted OK: api_key len={len(api_key)}, api_secret len={len(api_secret)}")
        
        # Now check Binance
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
                print(f"Futures response: {fapi}")
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
                print(f"Spot response: {account}")
        except Exception as e:
            print(f"Spot check error: {e}")
    except Exception as e:
        print(f"Decrypt error: {e}")

db.close()
