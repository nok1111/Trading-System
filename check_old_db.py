import sqlite3

for dbfile in ["test.db", "migrations.db"]:
    path = rf"c:\Users\nokturno\Desktop\TRADING PROJECT\{dbfile}"
    print(f"\n=== {dbfile} ===")
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        print("Tables:", tables)
        if "positions" in tables:
            c.execute("SELECT COUNT(*) FROM positions")
            print("Positions:", c.fetchone()[0])
            c.execute("SELECT * FROM positions LIMIT 5")
            cols = [d[0] for d in c.description]
            print("Columns:", cols)
            for r in c.fetchall():
                print(r)
        if "users" in tables:
            c.execute("SELECT id, username, email FROM users")
            print("Users:", c.fetchall())
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
