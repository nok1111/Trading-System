import sys

path = '/opt/trading-system/trading-client/app/api/routes/market.py'
with open(path, 'r') as f:
    content = f.read()

# Add debug print to ws_prices
old_prices = 'async def ws_prices(websocket: WebSocket, token: str = Query(...)):'
new_prices = 'async def ws_prices(websocket: WebSocket, token: str = Query(...)):\n    print("WS_PRICES_HANDLER_REACHED", flush=True)'
if old_prices in content and 'WS_PRICES_HANDLER_REACHED' not in content:
    content = content.replace(old_prices, new_prices, 1)

# Add debug print to ws_klines
old_klines = 'async def ws_klines(websocket: WebSocket, symbol: str, interval: str = "1m", token: str = Query(...)):'
new_klines = 'async def ws_klines(websocket: WebSocket, symbol: str, interval: str = "1m", token: str = Query(...)):\n    print("WS_KLINES_HANDLER_REACHED", flush=True)'
if old_klines in content and 'WS_KLINES_HANDLER_REACHED' not in content:
    content = content.replace(old_klines, new_klines, 1)

with open(path, 'w') as f:
    f.write(content)
print("Debug prints added")
