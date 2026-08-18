"""Minimal WS test - bypass all middleware."""
import sys
sys.path.insert(0, '/opt/trading-system/trading-client')

import asyncio
import websockets
import json

# Test 1: Direct WS to the running app
async def test_running_app():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTAwNDY4fQ.3weiHb1Q84_LaRjQ-Xao9kNPCkIzDMAG9rLLEHR0gI0"
    url = f"ws://localhost:8080/api/ws/prices?token={token}"
    print(f"Test 1: Connecting to running app {url[:60]}...")
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            print("  CONNECTED!")
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"  Message: {msg[:100]}")
    except Exception as e:
        print(f"  FAILED: {e}")

# Test 2: Create a minimal app and test WS
async def test_minimal_app():
    from fastapi import FastAPI, WebSocket, Query
    import uvicorn
    import threading
    import time

    app = FastAPI()

    @app.websocket("/ws/test")
    async def ws_test(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    # Start server in thread
    config = uvicorn.Config(app, host="127.0.0.1", port=18099, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)

    url = "ws://127.0.0.1:18099/ws/test"
    print(f"\nTest 2: Connecting to minimal app {url}...")
    try:
        async with websockets.connect(url, open_timeout=5) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"  CONNECTED! Message: {msg}")
    except Exception as e:
        print(f"  FAILED: {e}")

    server.should_exit = True

asyncio.run(test_running_app())
asyncio.run(test_minimal_app())
