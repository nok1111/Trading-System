import psycopg2
conn = psycopg2.connect("host=localhost dbname=trading_system user=trading_app password=Tr4d1ngApp2026!")
cur = conn.cursor()
cur.execute("SELECT id, status, closed_at, metadata_json FROM positions WHERE id = 24")
r = cur.fetchone()
print("Position #24:", r)
conn.close()
