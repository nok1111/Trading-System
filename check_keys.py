import sqlite3
db = sqlite3.connect(r"C:\Users\nokturno\Desktop\TRADING PROJECT\trading.db")
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

for t in tables:
    if 'user' in t.lower():
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in cur.fetchall()]
        print(f"\n{t} columns: {cols}")
        cur.execute(f"SELECT * FROM {t}")
        for row in cur.fetchall():
            print(f"  row: {row}")
db.close()
