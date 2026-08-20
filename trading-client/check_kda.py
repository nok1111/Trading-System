import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, opened_at FROM positions WHERE symbol LIKE %s ORDER BY id DESC LIMIT 10", ("%KDA%",))
rows = cur.fetchall()
for r in rows:
    print(r)
if not rows:
    print("No KDA positions found")
# Also check recent positions
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, opened_at FROM positions ORDER BY id DESC LIMIT 10")
print("\nRecent positions:")
for r in cur.fetchall():
    print(r)
conn.close()
