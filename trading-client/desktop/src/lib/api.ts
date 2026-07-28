const API_BASE = "http://localhost:18652";

// In-memory cache for GET requests with TTL
const _cache = new Map<string, { data: any; expires: number }>();
const DEFAULT_TTL = 30_000; // 30 seconds

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

  const r = await fetch(API_BASE + path, { ...opts, headers });

  if (r.status === 401) {
    console.log("API 401 on", path, "token:", authToken ? "yes" : "no");
    setAuthToken(null);
    window.dispatchEvent(new CustomEvent("auth-logout"));
    throw new Error("Sesión expirada");
  }
  if (r.status === 403) {
    const e = await r.json().catch(() => ({ detail: "Error" }));
    throw new Error(e.detail || "Suscripción inactiva");
  }
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "Error" }));
    throw new Error(e.detail || "Error");
  }
  const data = await r.json();

  // Cache successful GET responses
  if (method === "GET") {
    cacheSet(path, data);
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

  const r = await fetch(authServerUrl + path, { ...opts, headers });
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
