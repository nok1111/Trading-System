// In dev mode (Vite), the proxy handles /api -> VPS, so API_BASE = ""
// In production (Tauri), there's no proxy, so point directly to the VPS
const API_BASE = import.meta.env.PROD ? "http://76.13.180.80:8080" : "";

// In production (Tauri webview), use the Tauri HTTP plugin's fetch to bypass
// webview security restrictions. In dev (browser), use the native fetch.
import { fetch as tauriFetch } from "@tauri-apps/plugin-http";

const _fetch: typeof fetch = import.meta.env.PROD ? tauriFetch : fetch;

// Export for use in other files that call fetch directly
export { _fetch as fetch };

// In-memory cache for GET requests with TTL
const _cache = new Map<string, { data: any; expires: number }>();

// Per-endpoint TTL configuration (in ms)
const TTL_RULES: { pattern: string; ttl: number }[] = [
  // Fast-changing data (balance, positions, orders)
  { pattern: "/api/snapshots", ttl: 15_000 },
  { pattern: "/api/positions", ttl: 15_000 },
  { pattern: "/api/orders", ttl: 15_000 },
  // Market data
  { pattern: "/api/klines/", ttl: 60_000 },
  { pattern: "/api/market/movers", ttl: 60_000 },
  { pattern: "/api/prices/live", ttl: 5_000 },
  // Intelligence — slow changing
  { pattern: "/api/intelligence/fear-greed", ttl: 300_000 },
  { pattern: "/api/intelligence/dominance", ttl: 300_000 },
  { pattern: "/api/intelligence/market-overview", ttl: 300_000 },
  { pattern: "/api/intelligence/macro-events", ttl: 600_000 },
  { pattern: "/api/intelligence/daily-report", ttl: 300_000 },
  { pattern: "/api/intelligence/whale-activity", ttl: 120_000 },
  { pattern: "/api/intelligence/news", ttl: 120_000 },
  // Technical signals
  { pattern: "/api/intelligence/signals/technical", ttl: 60_000 },
  // AI Agent — near real-time
  { pattern: "/api/ai-agent/log", ttl: 2_000 },
  { pattern: "/api/ai-agent/status", ttl: 2_000 },
  { pattern: "/api/ai-agent/stats", ttl: 8_000 },
  { pattern: "/api/ai-agent/plan", ttl: 30_000 },
];
const DEFAULT_TTL = 30_000; // 30 seconds

function getTtlForPath(path: string): number {
  for (const rule of TTL_RULES) {
    if (path.startsWith(rule.pattern)) return rule.ttl;
  }
  return DEFAULT_TTL;
}

export function cacheGet<T>(path: string): T | null {
  const entry = _cache.get(path);
  if (entry && entry.expires > Date.now()) return entry.data as T;
  if (entry) _cache.delete(path);
  return null;
}

export function cacheSet(path: string, data: any, ttl: number = DEFAULT_TTL) {
  _cache.set(path, { data, expires: Date.now() + ttl });
}

export function cacheInvalidate(pathPrefix: string) {
  for (const key of _cache.keys()) {
    if (key.startsWith(pathPrefix)) _cache.delete(key);
  }
}

// Read token from localStorage on module init (survives Vite hot reloads)
let authToken: string | null = null;
try { authToken = localStorage.getItem("jwt"); } catch {}

export function setAuthToken(token: string | null) {
  authToken = token;
  // Clear all cached API responses when user changes (login/logout)
  _cache.clear();
  try {
    if (token) {
      localStorage.setItem("jwt", token);
    } else {
      localStorage.removeItem("jwt");
    }
  } catch {}
}

export function getAuthToken(): string | null {
  return authToken;
}

export async function api<T = any>(
  path: string,
  opts: RequestInit = {}
): Promise<T> {
  const method = (opts.method || "GET").toUpperCase();

  // Invalidate cache on mutations
  if (method !== "GET") {
    cacheInvalidate(path.split("?")[0]);
  }

  // Check cache for GET
  if (method === "GET") {
    const cached = cacheGet<T>(path);
    if (cached !== null) return cached;
  }

  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string>),
  };
  if (authToken) headers["Authorization"] = "Bearer " + authToken;
  if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";

  const r = await _fetch(API_BASE + path, { ...opts, headers } as any);

  if (r.status === 401) {
    console.log("API 401 on", path, "token:", authToken ? "yes" : "no");
    // Don't auto-logout on every 401 — only if we actually have a token
    // and the auth server rejected it. A 401 without token means the endpoint
    // requires auth and we're not logged in yet (caller should handle).
    if (authToken) {
      // Verify if token is actually invalid by checking with auth server
      // Only logout if token is truly invalid, not on transient failures
      try {
        const verifyResp = await _fetch(
          (localStorage.getItem("authServerUrl") || "http://76.13.180.80:8000") + "/api/auth/me",
          { headers: { Authorization: "Bearer " + authToken } } as any
        );
        if (verifyResp.status === 401 || verifyResp.status === 403) {
          setAuthToken(null);
          window.dispatchEvent(new CustomEvent("auth-logout"));
        }
      } catch {
        // Auth server unreachable — don't logout, just throw
      }
    }
    throw new Error("No autenticado");
  }
  if (r.status === 403) {
    const e = await r.json().catch(() => ({ detail: "Error" }));
    // Only logout on 403 if it's a subscription/license issue
    if (e.detail && e.detail.includes("Suscripción")) {
      setAuthToken(null);
      window.dispatchEvent(new CustomEvent("auth-logout"));
    }
    throw new Error(e.detail || "Suscripción inactiva");
  }
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "Error" }));
    throw new Error(e.detail || "Error");
  }
  const data = await r.json();

  // Cache successful GET responses
  if (method === "GET") {
    cacheSet(path, data, getTtlForPath(path));
  }

  return data;
}

export async function authApi<T = any>(
  path: string,
  opts: RequestInit = {}
): Promise<T> {
  const authServerUrl =
    localStorage.getItem("authServerUrl") || "http://76.13.180.80:8000";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  if (authToken) headers["Authorization"] = "Bearer " + authToken;

  const r = await _fetch(authServerUrl + path, { ...opts, headers } as any);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "Error" }));
    throw new Error(e.detail || "Error");
  }
  return r.json();
}

export function getAuthServerUrl(): string {
  return localStorage.getItem("authServerUrl") || "http://76.13.180.80:8000";
}

export function setAuthServerUrl(url: string) {
  localStorage.setItem("authServerUrl", url);
}
