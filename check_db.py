import sqlite3

conn = sqlite3.connect(r"c:\Users\nokturno\Desktop\TRADING PROJECT\trading.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tables:", tables)

for t in tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    count = c.fetchone()[0]
    print(f"  {t}: {count} rows")
    if t in ("positions", "trades", "orders") and count > 0:
        c.execute(f"SELECT * FROM {t} LIMIT 3")
        cols = [d[0] for d in c.description]
        print(f"    Columns: {cols}")
        for row in c.fetchall():
            print(f"    {row}")

conn.close()
