import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, stop_loss, take_profit, opened_at FROM positions WHERE symbol LIKE '%KDA%' ORDER BY id DESC LIMIT 5")
print("KDA positions:")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, opened_at FROM positions ORDER BY id DESC LIMIT 5")
print("\nRecent positions:")
for r in cur.fetchall():
    print(r)
conn.close()
