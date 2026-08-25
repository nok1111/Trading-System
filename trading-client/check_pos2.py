import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, stop_loss, take_profit, opened_at FROM positions WHERE status='open' ORDER BY id DESC LIMIT 10")
print("Open positions:")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, stop_loss, take_profit, opened_at FROM positions ORDER BY id DESC LIMIT 5")
print("\nRecent positions (any status):")
for r in cur.fetchall():
    print(r)
cur.execute("SELECT id, symbol, side, status, quantity, broker_order_id, client_order_id FROM orders WHERE symbol LIKE '%LINK%' ORDER BY id DESC LIMIT 5")
print("\nLINK orders:")
for r in cur.fetchall():
    print(r)
conn.close()
