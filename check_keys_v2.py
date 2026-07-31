import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")
from app.database.session import SessionLocal
from app.database.models.position import Position
from sqlalchemy import text

# Use SessionLocal directly (it has the correct DB URL)
db = SessionLocal()

# Show position
ps = db.query(Position).filter(Position.symbol.ilike("%DOGE%"), Position.status == "open").all()
for p in ps:
    print(f"POS: id={p.id} symbol={p.symbol} qty={p.quantity} meta={p.metadata_json}")

# Query user_settings using the session's connection
result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user_settings' ORDER BY ordinal_position"))
cols = [r[0] for r in result]
print(f"user_settings columns: {cols}")

result = db.execute(text("SELECT * FROM user_settings LIMIT 1"))
row = result.fetchone()
if row:
    colnames = list(result.keys())
    api_key_enc = None
    api_secret_enc = None
    for i, cn in enumerate(colnames):
        val = row[i]
        if val and "binance" in cn.lower() and ("key" in cn.lower() or "secret" in cn.lower()):
            print(f"  {cn} = (present, len={len(str(val))})")
            if "api_key" in cn.lower() and "secret" not in cn.lower():
                api_key_enc = val
            elif "api_secret" in cn.lower() or "secret" in cn.lower():
                api_secret_enc = val
        elif "binance" in cn.lower():
            print(f"  {cn} = (empty)")
    
    if api_key_enc and api_secret_enc:
        from app.services.crypto import decrypt
        api_key = decrypt(api_key_enc)
        api_secret = decrypt(api_secret_enc)
        print(f"API key len={len(api_key)}, secret len={len(api_secret)}")
        
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
            doge_f = [p for p in fapi if "DOGE" in p.get("symbol", "") and float(p.get("positionAmt", 0)) != 0]
            if doge_f:
                for p in doge_f:
                    print(f"FUTURES: symbol={p['symbol']} qty={p['positionAmt']} entry={p['entryPrice']} mark={p['markPrice']}")
            else:
                print("No DOGE futures positions on Binance")
        except Exception as e:
            print(f"Futures check error: {e}")
        
        # Check spot
        try:
            account = signed_get("https://api.binance.com", "/api/v3/account")
            doge = [b for b in account.get("balances", []) if b["asset"] == "DOGE" and (float(b["free"]) > 0 or float(b["locked"]) > 0)]
            if doge:
                for b in doge:
                    print(f"SPOT: asset={b['asset']} free={b['free']} locked={b['locked']}")
            else:
                print("No DOGE spot balance on Binance")
        except Exception as e:
            print(f"Spot check error: {e}")
else:
    print("No user_settings row found")

db.close()
