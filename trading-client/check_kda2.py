import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
cur.execute("SELECT id, symbol, side, status, quantity, entry_price, stop_loss, take_profit, opened_at, metadata_json FROM positions WHERE symbol LIKE '%KDA%' ORDER BY id DESC LIMIT 3")
for r in cur.fetchall():
    print(r)
conn.close()
