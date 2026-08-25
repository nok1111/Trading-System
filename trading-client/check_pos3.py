import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
# Check all LINK orders
cur.execute("SELECT id, symbol, side, status, quantity, broker_order_id, client_order_id, idempotency_key FROM orders WHERE symbol LIKE '%LINK%' ORDER BY id ASC")
print("ALL LINK orders:")
for r in cur.fetchall():
    print(r)
# Check if there are any sell orders for LINK
cur.execute("SELECT id, symbol, side, status, quantity, broker_order_id FROM orders WHERE symbol LIKE '%LINK%' AND side IN ('sell', 'SELL') ORDER BY id ASC")
print("\nLINK SELL orders:")
for r in cur.fetchall():
    print(r)
conn.close()
