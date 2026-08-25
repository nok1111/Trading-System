import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, stop_loss, take_profit, opened_at FROM positions WHERE symbol LIKE '%LINK%' OR id > 24 ORDER BY id DESC LIMIT 10")
print("LINK/recent positions:")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, stop_loss, take_profit, opened_at FROM positions WHERE status='open' ORDER BY id DESC LIMIT 10")
print("\nOpen positions:")
for r in cur.fetchall():
    print(r)
conn.close()
