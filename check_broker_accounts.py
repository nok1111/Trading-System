import sys, os, httpx, hmac, hashlib, time, urllib.parse
sys.path.insert(0, "/opt/trading-system")
from app.database.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check broker_accounts
result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='broker_accounts' ORDER BY ordinal_position"))
cols = [r[0] for r in result]
print(f"broker_accounts columns: {cols}")

result = db.execute(text("SELECT * FROM broker_accounts LIMIT 5"))
rows = result.fetchall()
colnames = list(result.keys())
print(f"Rows: {len(rows)}")
for row in rows:
    for i, cn in enumerate(colnames):
        val = row[i]
        if val is not None:
            if "api" in cn.lower() or "secret" in cn.lower() or "key" in cn.lower() or "cred" in cn.lower():
                print(f"  {cn} = (present, len={len(str(val))})")
                if "enc" in cn.lower():
                    try:
                        from app.services.crypto import decrypt
                        dec = decrypt(val)
                        if len(dec) > 10:
                            print(f"    decrypted: {dec[:8]}... (len={len(dec)})")
                    except Exception as e:
                        print(f"    decrypt error: {e}")
            else:
                print(f"  {cn} = {val}")
    print("---")

# Also check user_profiles
result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user_profiles' ORDER BY ordinal_position"))
cols = [r[0] for r in result]
print(f"user_profiles columns: {cols}")

result = db.execute(text("SELECT * FROM user_profiles LIMIT 1"))
row = result.fetchone()
if row:
    colnames = list(result.keys())
    for i, cn in enumerate(colnames):
        print(f"  {cn} = {row[i]}")

db.close()
