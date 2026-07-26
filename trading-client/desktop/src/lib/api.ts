const API_BASE = "http://localhost:18652";

let authToken: string | null = localStorage.getItem("jwt");

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem("jwt", token);
  } else {
    localStorage.removeItem("jwt");
  }
}

export function getAuthToken(): string | null {
  return authToken;
}

export async function api<T = any>(
  path: string,
  opts: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string>),
  };
  if (authToken) headers["Authorization"] = "Bearer " + authToken;
  if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";

  const r = await fetch(API_BASE + path, { ...opts, headers });

  if (r.status === 401) {
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
  return r.json();
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
