"""Test AI config save/load flow end-to-end."""
import httpx
import json

AUTH_URL = "http://76.13.180.80:8000"
API_URL = "http://76.13.180.80:8080"

# Login
r = httpx.post(f"{AUTH_URL}/api/auth/login", json={
    "email": "nokturnog@gmail.com",
    "password": "panicopain1",
}, timeout=10)
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 70)
print("AI CONFIG PERSISTENCE TESTS")
print("=" * 70)

# 1. Get current keys (should show current state)
print("\n--- 1. GET /api/settings/keys (initial state) ---")
r = httpx.get(f"{API_URL}/api/settings/keys", headers=headers, timeout=10)
print(f"  Status: {r.status_code}")
data = r.json()
print(f"  ai_provider: {data.get('ai_provider')}")
print(f"  ai_model: {data.get('ai_model')}")
print(f"  last_model_used: {data.get('last_model_used')}")
print(f"  last_ai_provider_used: {data.get('last_ai_provider_used')}")
print(f"  groq_api_key_set: {data.get('groq_api_key_set')}")
print(f"  gemini_api_key_set: {data.get('gemini_api_key_set')}")

# 2. Save AI config (provider + model, no key)
print("\n--- 2. POST /api/settings/ai-config (gemini + gemini-2.0-flash) ---")
r = httpx.post(f"{API_URL}/api/settings/ai-config", headers=headers, json={
    "provider": "gemini",
    "model": "gemini-2.0-flash",
}, timeout=10)
print(f"  Status: {r.status_code}")
print(f"  Response: {r.json()}")

# 3. Verify it was saved
print("\n--- 3. GET /api/settings/keys (verify save) ---")
r = httpx.get(f"{API_URL}/api/settings/keys", headers=headers, timeout=10)
data = r.json()
print(f"  ai_provider: {data.get('ai_provider')}")
print(f"  ai_model: {data.get('ai_model')}")
print(f"  last_model_used: {data.get('last_model_used')}")
print(f"  last_ai_provider_used: {data.get('last_ai_provider_used')}")
assert data.get("ai_provider") == "gemini", f"Expected gemini, got {data.get('ai_provider')}"
assert data.get("ai_model") == "gemini-2.0-flash", f"Expected gemini-2.0-flash, got {data.get('ai_model')}"
assert data.get("last_model_used") == "gemini-2.0-flash"
assert data.get("last_ai_provider_used") == "gemini"
print("  ✓ All assertions passed!")

# 4. Save with a different provider
print("\n--- 4. POST /api/settings/ai-config (groq + llama-3.3-70b-versatile) ---")
r = httpx.post(f"{API_URL}/api/settings/ai-config", headers=headers, json={
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",
}, timeout=10)
print(f"  Status: {r.status_code}")
print(f"  Response: {r.json()}")

# 5. Verify
print("\n--- 5. GET /api/settings/keys (verify groq) ---")
r = httpx.get(f"{API_URL}/api/settings/keys", headers=headers, timeout=10)
data = r.json()
print(f"  ai_provider: {data.get('ai_provider')}")
print(f"  ai_model: {data.get('ai_model')}")
print(f"  last_model_used: {data.get('last_model_used')}")
assert data.get("ai_provider") == "groq"
assert data.get("ai_model") == "llama-3.3-70b-versatile"
print("  ✓ All assertions passed!")

# 6. Get AI agent status (should show saved provider/model)
print("\n--- 6. GET /api/ai-agent/status ---")
r = httpx.get(f"{API_URL}/api/ai-agent/status", headers=headers, timeout=10)
data = r.json()
print(f"  provider: {data.get('provider')}")
print(f"  model: {data.get('model')}")
print(f"  saved_provider: {data.get('saved_provider')}")
print(f"  saved_model: {data.get('saved_model')}")

# 7. Get AI agent plan (should show saved config)
print("\n--- 7. GET /api/ai-agent/plan ---")
r = httpx.get(f"{API_URL}/api/ai-agent/plan", headers=headers, timeout=10)
data = r.json()
print(f"  saved_provider: {data.get('saved_provider')}")
print(f"  saved_model: {data.get('saved_model')}")
print(f"  has_groq_key: {data.get('has_groq_key')}")
print(f"  has_gemini_key: {data.get('has_gemini_key')}")

# 8. Test analyze-positions (should use saved config)
print("\n--- 8. POST /api/ai-agent/analyze-positions (should use saved config) ---")
r = httpx.post(f"{API_URL}/api/ai-agent/analyze-positions", headers=headers, json={
    "positions": [],
    "broker": "paper",
}, timeout=10)
print(f"  Status: {r.status_code}")
print(f"  Response: {r.text[:300]}")

print(f"\n{'=' * 70}")
print("AI CONFIG PERSISTENCE TESTS COMPLETE")
print(f"{'=' * 70}")
