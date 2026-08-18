"""
Comprehensive multi-broker test + Alvora quick-prompt test.
Tests all 21 brokers, multi-broker combinations, and all Alvora quick-prompts.
"""
import time
import json
import requests
import concurrent.futures

BASE = "http://localhost:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTc5OTQzfQ.yki9p5i282WuQyPyZOGEp5ZkPwh1Py5CXBUcPqoRb3k"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

ALL_BROKERS = [
    "binance", "bybit", "kraken", "coinbase", "okx", "kucoin", "bitget",
    "mexc", "gate", "htx", "bitfinex", "poloniex", "gemini", "bitstamp",
    "bithumb", "okcoin", "ascendex", "bingx", "coinex", "crypto_com", "upbit"
]

bugs = []
results = []

def test(name, method, path, body=None, timeout=20, expected=200):
    t0 = time.time()
    try:
        if method == "GET":
            r = requests.get(BASE + path, headers=HEADERS, timeout=timeout)
        elif method == "POST":
            r = requests.post(BASE + path, headers=HEADERS, json=body, timeout=timeout)
        elif method == "DELETE":
            r = requests.delete(BASE + path, headers=HEADERS, timeout=timeout)
        ms = round((time.time() - t0) * 1000)
        ok = r.status_code == expected
        try:
            data = r.json()
        except:
            data = r.text[:200]
        results.append({"name": name, "status": r.status_code, "ms": ms, "ok": ok})
        if not ok:
            preview = json.dumps(data)[:150] if isinstance(data, dict) else str(data)[:150]
            bugs.append(f"{name}: {r.status_code} (expected {expected}) in {ms}ms — {preview}")
            print(f"  FAIL {name}: {r.status_code} in {ms}ms — {preview[:80]}")
        else:
            print(f"  OK   {name}: {r.status_code} in {ms}ms")
        return r.status_code, data, ms
    except Exception as e:
        ms = round((time.time() - t0) * 1000)
        results.append({"name": name, "status": 0, "ms": ms, "ok": False})
        bugs.append(f"{name}: EXCEPTION — {e}")
        print(f"  FAIL {name}: EXCEPTION in {ms}ms — {e}")
        return 0, str(e), ms

def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")

# ============================================================
# 1. TEST EACH BROKER — PUBLIC ENDPOINTS (no creds needed)
# ============================================================
section("1. PUBLIC ENDPOINTS PER BROKER (ticker, klines, movers, symbols)")

for broker_id in ALL_BROKERS:
    print(f"\n  --- {broker_id} ---")
    # Ticker (public — no creds)
    test(f"{broker_id} ticker", "GET", f"/api/broker/{broker_id}/ticker?symbol=BTC/USDT")
    # Klines (public)
    test(f"{broker_id} klines", "GET", f"/api/broker/{broker_id}/klines?symbol=BTC/USDT&interval=1h&limit=5")
    # Movers (public — uses broker's public ticker API)
    test(f"{broker_id} movers", "GET", f"/api/broker/{broker_id}/movers?limit=5")
    # Symbols (public)
    test(f"{broker_id} symbols", "GET", f"/api/broker/{broker_id}/symbols?limit=10")

# ============================================================
# 2. TEST EACH BROKER — PRIVATE ENDPOINTS (with creds, should fail gracefully)
# ============================================================
section("2. PRIVATE ENDPOINTS PER BROKER (balance, positions — should fail gracefully without creds)")

for broker_id in ALL_BROKERS:
    print(f"\n  --- {broker_id} ---")
    # Balance (requires creds — should return error, not 500)
    s, d, m = test(f"{broker_id} balance", "GET", f"/api/broker/{broker_id}/balance", expected=200)
    if s == 200 and isinstance(d, dict) and "error" in d:
        print(f"    -> Graceful error: {d.get('error', '')[:80]}")

# ============================================================
# 3. MULTI-BROKER COMPATIBILITY — Parallel calls to different brokers
# ============================================================
section("3. MULTI-BROKER PARALLEL CALLS (compatibility test)")

# Call ticker on 5 different brokers simultaneously
parallel_brokers = ["binance", "bybit", "kraken", "okx", "kucoin"]
def parallel_ticker(bid):
    t0 = time.time()
    try:
        r = requests.get(f"{BASE}/api/broker/{bid}/ticker?symbol=BTC/USDT", headers=HEADERS, timeout=15)
        ms = round((time.time() - t0) * 1000)
        return bid, r.status_code, ms, r.json() if r.headers.get("content-type","").startswith("application/json") else r.text[:100]
    except Exception as e:
        return bid, 0, round((time.time() - t0) * 1000), str(e)

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    futures = [pool.submit(parallel_ticker, bid) for bid in parallel_brokers]
    for f in concurrent.futures.as_completed(futures):
        bid, status, ms, data = f.result()
        ok = status == 200
        if not ok:
            bugs.append(f"Parallel {bid} ticker: {status} in {ms}ms")
        print(f"  {'OK' if ok else 'FAIL'} {bid} ticker (parallel): {status} in {ms}ms")

# ============================================================
# 4. ALVORA QUICK-PROMPTS — Test all 6 prompts
# ============================================================
section("4. ALVORA QUICK-PROMPTS (all 6)")

QUICK_PROMPTS = [
    ("portfolio_review", "Revisa mi portafolio actual. Como esta mi exposicion y mi P&L? Hay algo que deberia cambiar?"),
    ("market_now", "Como esta el mercado ahora mismo? Cual es el sentimiento y hay oportunidades claras para mi perfil?"),
    ("position_advice", "Analiza mis posiciones abiertas una por una. Cuales deberia mantener, cuales cerrar y por que?"),
    ("risk_check", "Hazme un chequeo de riesgo. Estoy expuesto a algo peligroso? Mi stop-loss y take-profit estan bien configurados?"),
    ("opportunities", "Hay oportunidades de trading hoy que encajen con mi perfil? Dame concrete: simbolo, razon, SL y TP sugeridos."),
    ("improve_strategy", "Segun mi perfil y mi historial reciente, como podria mejorar mi estrategia de trading?"),
]

alvora_results = []
for prompt_id, message in QUICK_PROMPTS:
    print(f"\n  --- {prompt_id} ---")
    s, d, m = test(f"Alvora: {prompt_id}", "POST", "/api/alvora/chat", body={"message": message}, timeout=60)
    if s == 200 and isinstance(d, dict):
        reply = d.get("reply", "")
        actions = d.get("actions", [])
        provider = d.get("provider", "")
        latency = d.get("latency_ms", 0)
        has_error = d.get("error") is not None
        alvora_results.append({
            "prompt": prompt_id,
            "reply_len": len(reply),
            "actions_count": len(actions),
            "provider": provider,
            "latency_ms": latency,
            "has_error": has_error,
        })
        print(f"    Reply: {len(reply)} chars, Actions: {len(actions)}, Provider: {provider}, Latency: {latency}ms")
        if actions:
            for a in actions:
                print(f"    Action: {a.get('type')} — {json.dumps(a.get('params',{}))[:80]}")
        # Check if reply mentions broker
        if "broker" in reply.lower() or "binance" in reply.lower():
            print(f"    -> Mentions broker: YES")
        else:
            print(f"    -> Mentions broker: NO")

# ============================================================
# 5. ALVORA MULTI-BROKER AWARENESS TEST
# ============================================================
section("5. ALVORA MULTI-BROKER AWARENESS")

# Ask Alvora about specific brokers
multi_broker_msgs = [
    ("ask_which_broker", "En que broker tengo mis posiciones? Tengo cuentas en varios?"),
    ("ask_bybit", "Puedes revisar mi balance en Bybit?"),
    ("ask_multi_broker", "Tengo posiciones en diferentes brokers? Cual es mi exposicion total?"),
]

for prompt_id, message in multi_broker_msgs:
    print(f"\n  --- {prompt_id} ---")
    s, d, m = test(f"Alvora: {prompt_id}", "POST", "/api/alvora/chat", body={"message": message}, timeout=60)
    if s == 200 and isinstance(d, dict):
        reply = d.get("reply", "")
        print(f"    Reply: {reply[:200]}...")

# ============================================================
# SUMMARY
# ============================================================
section("SUMMARY")
total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = sum(1 for r in results if not r["ok"])
avg_ms = round(sum(r["ms"] for r in results) / total) if total else 0

print(f"\nTotal tests: {total} | Passed: {passed} | Failed: {failed}")
print(f"Average response: {avg_ms}ms")

print(f"\n--- Alvora Quick-Prompt Results ---")
for r in alvora_results:
    status = "OK" if not r["has_error"] else "ERROR"
    print(f"  [{status}] {r['prompt']}: {r['reply_len']} chars, {r['actions_count']} actions, {r['latency_ms']}ms ({r['provider']})")

if bugs:
    print(f"\n{'='*70}")
    print(f"  BUGS FOUND: {len(bugs)}")
    print(f"{'='*70}")
    for b in bugs:
        print(f"  - {b}")
else:
    print("\n  No bugs found!")

# Save results
with open("/tmp/multi_broker_results.json", "w") as f:
    json.dump({"results": results, "bugs": bugs, "alvora": alvora_results, "summary": {"total": total, "passed": passed, "failed": failed}}, f, indent=2)
