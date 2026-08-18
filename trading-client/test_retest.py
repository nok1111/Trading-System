"""Focused re-test: CCXT movers fix + Alvora quick-prompts timeout fix."""
import time, json, requests

BASE = "http://localhost:8080"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3MTgwNjgwfQ.GSNQNqzoO5hZ2nWSahOU0IG3eZH74dCNoWO1As8g48k"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

bugs = []

# 1. Test CCXT movers on all brokers
print("="*60)
print("  1. CCXT MOVERS FIX VERIFICATION")
print("="*60)
for bid in ["binance", "bybit", "kraken", "okx", "kucoin", "bitget", "mexc", "gate", "bingx", "coinex", "upbit"]:
    t0 = time.time()
    try:
        r = requests.get(f"{BASE}/api/broker/{bid}/movers?limit=3", headers=H, timeout=20)
        ms = round((time.time()-t0)*1000)
        if r.status_code == 200:
            d = r.json()
            g = len(d.get("gainers", []))
            l = len(d.get("losers", []))
            print(f"  OK   {bid} movers: {r.status_code} in {ms}ms — {g} gainers, {l} losers")
        else:
            print(f"  FAIL {bid} movers: {r.status_code} in {ms}ms — {r.text[:80]}")
            bugs.append(f"{bid} movers: {r.status_code}")
    except Exception as e:
        print(f"  FAIL {bid} movers: EXCEPTION — {e}")
        bugs.append(f"{bid} movers: {e}")

# 2. Test Alvora quick-prompts (with 90s timeout to allow fallback)
print(f"\n{'='*60}")
print("  2. ALVORA QUICK-PROMPTS TIMEOUT FIX")
print("="*60)
PROMPTS = [
    ("portfolio_review", "Revisa mi portafolio actual. Como esta mi exposicion y mi P&L?"),
    ("market_now", "Como esta el mercado ahora mismo? Hay oportunidades?"),
    ("position_advice", "Analiza mis posiciones abiertas. Cuales mantener, cuales cerrar?"),
    ("risk_check", "Chequea mi riesgo. Stop-loss y take-profit bien configurados?"),
    ("opportunities", "Hay oportunidades hoy? Dame simbolo, razon, SL y TP."),
    ("improve_strategy", "Como podria mejorar mi estrategia de trading?"),
]

for pid, msg in PROMPTS:
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}/api/alvora/chat", headers=H, json={"message": msg}, timeout=90)
        ms = round((time.time()-t0)*1000)
        if r.status_code == 200:
            d = r.json()
            reply_len = len(d.get("reply", ""))
            actions = len(d.get("actions", []))
            provider = d.get("provider", "")
            error = d.get("error")
            has_error = "ERROR" if error else "OK"
            print(f"  [{has_error}] {pid}: {ms}ms, {reply_len} chars, {actions} actions ({provider})")
            if error:
                bugs.append(f"Alvora {pid}: error={error[:100]}")
        else:
            print(f"  FAIL {pid}: {r.status_code} in {ms}ms")
            bugs.append(f"Alvora {pid}: {r.status_code}")
    except Exception as e:
        ms = round((time.time()-t0)*1000)
        print(f"  FAIL {pid}: TIMEOUT/EXCEPTION in {ms}ms — {e}")
        bugs.append(f"Alvora {pid}: timeout/exception")

# 3. Alvora multi-broker awareness
print(f"\n{'='*60}")
print("  3. ALVORA MULTI-BROKER AWARENESS")
print("="*60)
for pid, msg in [
    ("which_broker", "En que broker tengo mis posiciones?"),
    ("bybit_balance", "Puedes revisar mi balance en Bybit?"),
    ("multi_exposure", "Tengo posiciones en diferentes brokers?"),
]:
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}/api/alvora/chat", headers=H, json={"message": msg}, timeout=90)
        ms = round((time.time()-t0)*1000)
        if r.status_code == 200:
            d = r.json()
            reply = d.get("reply", "")
            mentions_broker = "broker" in reply.lower() or "binance" in reply.lower()
            print(f"  OK   {pid}: {ms}ms, mentions_broker={mentions_broker}")
            print(f"    Reply: {reply[:150]}...")
        else:
            print(f"  FAIL {pid}: {r.status_code}")
            bugs.append(f"Alvora {pid}: {r.status_code}")
    except Exception as e:
        print(f"  FAIL {pid}: {e}")
        bugs.append(f"Alvora {pid}: {e}")

print(f"\n{'='*60}")
print(f"  SUMMARY: {len(bugs)} bugs")
print("="*60)
for b in bugs:
    print(f"  - {b}")
if not bugs:
    print("  ALL TESTS PASSED!")
