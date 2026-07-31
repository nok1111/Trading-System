import httpx
r = httpx.get('https://api.binance.com/api/v3/exchangeInfo?symbol=DOGEUSDT', timeout=10)
data = r.json()
filters = data['symbols'][0]['filters']
for f in filters:
    if f['filterType'] in ('LOT_SIZE', 'PRICE_FILTER', 'MIN_NOTIONAL', 'NOTIONAL'):
        print(f"{f['filterType']}: {f}")
