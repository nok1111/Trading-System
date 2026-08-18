"""Multi-broker step-by-step simulation + Alvora action execution."""
import time, json, requests

BASE = "http://localhost:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTgxMDUxfQ.jHIHgjPJ_6yNkpSzqSM8eZ8jILhuaSIcIp6DRPTYmEI"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
bugs = []

def call(method, path, body=None, timeout=30):
    t0 = time.time()
    try:
        if method == "GET": r = requests.get(BASE+path, headers=H, timeout=timeout)
        elif method == "POST": r = requests.post(BASE+path, headers=H, json=body, timeout=timeout)
        elif method == "PATCH": r = requests.patch(BASE+path, headers=H, json=body, timeout=timeout)
        elif method == "DELETE": r = requests.delete(BASE+path, headers=H, timeout=timeout)
        ms = round((time.time()-t0)*1000)
        try: d = r.json()
        except: d = r.text[:200]
        return r.status_code, d, ms
    except Exception as e:
        return 0, str(e), round((time.time()-t0)*1000)

def check(name, s, d, ms, exp=200):
    ok = s == exp
    print(f"  {'OK' if ok else 'FAIL'} {name}: {s} in {ms}ms")
    if not ok:
        bugs.append(f"{name}: {s} — {str(d)[:100]}")
    return ok, d

def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")

# ============================================================
# FLOW 1: Multi-broker data fetch (simulating user switching brokers)
# ============================================================
section("FLOW 1: Multi-Broker Data Fetch (user switches between brokers)")

brokers_to_test = ["binance", "bybit", "kraken", "okx", "kucoin"]
for bid in brokers_to_test:
    print(f"\n  --- User selects {bid} ---")
    # User clicks on broker → fetch ticker, klines, symbols
    s, d, m = call("GET", f"/api/broker/{bid}/ticker?symbol=BTC/USDT")
    check(f"{bid} ticker", s, d, m)
    s, d, m = call("GET", f"/api/broker/{bid}/klines?symbol=BTC/USDT&interval=1h&limit=10")
    check(f"{bid} klines", s, d, m)
    s, d, m = call("GET", f"/api/broker/{bid}/symbols?limit=5")
    check(f"{bid} symbols", s, d, m)
    s, d, m = call("GET", f"/api/broker/{bid}/movers?limit=3")
    check(f"{bid} movers", s, d, m)

# ============================================================
# FLOW 2: Alvora chat with action proposal + execution
# ============================================================
section("FLOW 2: Alvora Chat -> Action -> Execute")

step = 1
print(f"\n  Step {step}: Ask Alvora for opportunity with action")
s, d, m = call("POST", "/api/alvora/chat", body={"message": "Dame una oportunidad concreta de trading. Genera la accion [ACTION:open_trade|...] con SL y TP."}, timeout=90)
check("Alvora chat (opportunity)", s, d, m)
if s == 200 and isinstance(d, dict):
    actions = d.get("actions", [])
    reply = d.get("reply", "")
    print(f"    Reply: {len(reply)} chars, Actions: {len(actions)}")
    for a in actions:
        print(f"    Action: {a.get('type')} — {json.dumps(a.get('params',{}))[:100]}")
    
    if actions:
        step += 1
        print(f"\n  Step {step}: Execute first action")
        action = actions[0]
        s2, d2, m2 = call("POST", "/api/alvora/execute", body={
            "action_type": action.get("type"),
            "params": action.get("params", {}),
        }, timeout=30)
        check(f"Execute {action.get('type')}", s2, d2, m2)
        if isinstance(d2, dict):
            print(f"    Result: {json.dumps(d2)[:150]}")
    else:
        print("    No actions proposed — checking if reply mentions why")
        if "rate" in reply.lower() or "quota" in reply.lower() or "error" in reply.lower():
            print("    -> AI provider rate limited (expected)")

# ============================================================
# FLOW 3: Alvora position management
# ============================================================
section("FLOW 3: Alvora Position Management")

print(f"\n  Step 1: Get current positions")
s, d, m = call("GET", "/api/positions")
check("Get positions", s, d, m)
if s == 200 and isinstance(d, list):
    print(f"    Found {len(d)} positions")
    for p in d[:3]:
        print(f"    - {p.get('symbol')} P&L={p.get('unrealized_pnl')} broker={p.get('broker_id','?')}")

print(f"\n  Step 2: Ask Alvora to analyze positions")
s, d, m = call("POST", "/api/alvora/chat", body={"message": "Analiza mis posiciones. Cuales mantener, cuales cerrar?"}, timeout=90)
check("Alvora position analysis", s, d, m)
if s == 200 and isinstance(d, dict):
    print(f"    Reply: {d.get('reply','')[:200]}...")

# ============================================================
# FLOW 4: Multi-broker parallel operations (compatibility)
# ============================================================
section("FLOW 4: Multi-Broker Parallel Operations")
import concurrent.futures

def parallel_broker_op(bid):
    """Simulate user fetching data from multiple brokers simultaneously."""
    results = []
    # Ticker
    s, d, m = call("GET", f"/api/broker/{bid}/ticker?symbol=ETH/USDT")
    results.append((f"{bid} ticker", s, m))
    # Klines
    s, d, m = call("GET", f"/api/broker/{bid}/klines?symbol=ETH/USDT&interval=15m&limit=5")
    results.append((f"{bid} klines", s, m))
    return results

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    futures = {pool.submit(parallel_broker_op, bid): bid for bid in ["binance", "bybit", "kraken", "okx", "mexc"]}
    for f in concurrent.futures.as_completed(futures):
        bid = futures[f]
        results = f.result()
        for name, s, m in results:
            ok = s == 200
            if not ok:
                bugs.append(f"Parallel {name}: {s}")
            print(f"  {'OK' if ok else 'FAIL'} {name} (parallel): {s} in {m}ms")

# ============================================================
# FLOW 5: Alvora multi-broker awareness
# ============================================================
section("FLOW 5: Alvora Multi-Broker Awareness")

msgs = [
    ("Tengo cuentas en varios brokers? Cuales?",
     "Should list all connected brokers"),
    ("Si tuviera Bybit y Binance, como decidirias en cual operar?",
     "Should explain multi-broker selection logic"),
    ("Puedes revisar mi balance en Kraken?",
     "Should say Kraken not connected"),
]

for msg, expected in msgs:
    print(f"\n  Msg: {msg[:50]}...")
    s, d, m = call("POST", "/api/alvora/chat", body={"message": msg}, timeout=90)
    check(f"Alvora: {msg[:30]}", s, d, m)
    if s == 200 and isinstance(d, dict):
        reply = d.get("reply", "")
        print(f"    Reply: {reply[:150]}...")
        print(f"    Expected: {expected}")

# ============================================================
# FLOW 6: Broker capabilities check (for trading compatibility)
# ============================================================
section("FLOW 6: Broker Capabilities Check")

for bid in ["binance", "bybit", "kraken", "okx", "kucoin", "bitget", "mexc"]:
    s, d, m = call("GET", f"/api/brokers")
    if s == 200 and isinstance(d, list):
        broker = next((b for b in d if b["brokerId"] == bid), None)
        if broker:
            caps = broker.get("capabilities", {})
            markets = broker.get("supportedMarkets", [])
            print(f"  {bid}: spot={caps.get('spot')}, futures={caps.get('futures')}, markets={markets}")

# ============================================================
# SUMMARY
# ============================================================
section("SUMMARY")
print(f"\n  Bugs found: {len(bugs)}")
for b in bugs:
    print(f"  - {b}")
if not bugs:
    print("  ALL FLOWS COMPLETED SUCCESSFULLY!")
