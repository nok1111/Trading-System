import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")
from app.database.session import SessionLocal
from sqlalchemy import text
from app.services.crypto import decrypt

db = SessionLocal()

# Get the first broker account for user_id=1
result = db.execute(text("SELECT id, user_id, broker_id, api_key_enc, api_secret_enc FROM broker_accounts WHERE broker_id='binance' AND status='CONNECTED_TRADING' ORDER BY created_at LIMIT 1"))
row = result.fetchone()
if not row:
    print("No broker account found")
    db.close()
    exit()

print(f"Broker account: id={row[0]} user_id={row[1]} broker={row[2]}")

# Try to decrypt
try:
    api_key = decrypt(row[3])
    api_secret = decrypt(row[4])
    print(f"Decrypted: api_key len={len(api_key)}, api_secret len={len(api_secret)}")
except Exception as e:
    print(f"Decrypt error: {e}")
    # Try without decrypt - maybe it's plain text?
    print(f"Raw api_key_enc: {row[3][:20]}...")
    print(f"Raw api_secret_enc: {row[4][:20]}...")
    
    # Check if it's base64 or Fernet
    import base64
    try:
        decoded = base64.b64decode(row[3])
        print(f"Base64 decoded: {decoded[:20]}...")
    except:
        print("Not base64")
    
    # Check the crypto module
    from app.services import crypto
    print(f"Crypto module: {dir(crypto)}")
    
    # Try with Fernet directly
    try:
        from cryptography.fernet import Fernet
        # Get the encryption key from env
        enc_key = os.environ.get("ENCRYPTION_KEY", os.environ.get("SECRET_KEY", ""))
        print(f"ENCRYPTION_KEY present: {bool(enc_key)}")
        if enc_key:
            f = Fernet(enc_key.encode() if isinstance(enc_key, str) else enc_key)
            api_key = f.decrypt(row[3].encode()).decode()
            api_secret = f.decrypt(row[4].encode()).decode()
            print(f"Fernet decrypted: api_key len={len(api_key)}, api_secret len={len(api_secret)}")
    except Exception as e2:
        print(f"Fernet error: {e2}")

db.close()
