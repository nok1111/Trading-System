"""Test WS connection directly on VPS."""
import asyncio
import websockets
import json

async def test():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTAwNDY4fQ.3weiHb1Q84_LaRjQ-Xao9kNPCkIzDMAG9rLLEHR0gI0"
    url = f"ws://localhost:8080/api/ws/klines/ETH/USDT?interval=1h&token={token}"
    print(f"Connecting to {url[:80]}...")
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            print("CONNECTED!")
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"First message: {msg[:200]}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        if hasattr(e, 'status_code'):
            print(f"Status code: {e.status_code}")
        if hasattr(e, 'headers'):
            print(f"Headers: {dict(e.headers)}")

asyncio.run(test())
