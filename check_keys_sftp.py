import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")
from app.database.session import SessionLocal
from app.database.models.position import Position
from sqlalchemy import create_engine, text

# Get DB URL from the session
db = SessionLocal()
db_url = str(db.bind.url)
print(f"DB URL: {db_url[:50]}...")
db.close()

# Create fresh engine
eng = create_engine(db_url)
with eng.connect() as conn:
    # Check user_settings for binance keys
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user_settings' ORDER BY ordinal_position"))
    cols = [r[0] for r in result]
    print(f"user_settings columns: {cols}")

    result = conn.execute(text("SELECT * FROM user_settings LIMIT 1"))
    row = result.fetchone()
    if row:
        colnames = list(result.keys())
        for i, cn in enumerate(colnames):
            val = row[i]
            if val and "binance" in cn.lower():
                print(f"  {cn} = (present, len={len(str(val))})")
                if "key" in cn.lower() or "secret" in cn.lower():
                    try:
                        from app.services.crypto import decrypt
                        dec = decrypt(val)
                        print(f"    decrypted len={len(dec)}")
                    except Exception as e:
                        print(f"    decrypt error: {e}")
            elif "binance" in cn.lower():
                print(f"  {cn} = (empty)")

    # Also check broker_accounts
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='broker_accounts' ORDER BY ordinal_position"))
    cols = [r[0] for r in result]
    print(f"broker_accounts columns: {cols}")

    result = conn.execute(text("SELECT * FROM broker_accounts LIMIT 5"))
    rows = result.fetchall()
    colnames = list(result.keys())
    for row in rows:
        for i, cn in enumerate(colnames):
            if row[i] and ("api" in cn.lower() or "secret" in cn.lower() or "key" in cn.lower()):
                print(f"  broker_accounts.{cn} = (present, len={len(str(row[i]))})")
                if "enc" in cn.lower():
                    try:
                        from app.services.crypto import decrypt
                        dec = decrypt(row[i])
                        print(f"    decrypted len={len(dec)}")
                    except Exception as e:
                        print(f"    decrypt error: {e}")
