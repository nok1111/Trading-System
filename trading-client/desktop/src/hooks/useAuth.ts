import { useCallback, useEffect, useState } from "react";
import { api, authApi, getAuthToken, setAuthToken } from "../lib/api";
import * as brokerApi from "../lib/brokerApi";

export interface User {
  id: number;
  email: string;
  username: string;
  subscription: string;
  created_at?: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authServerOk, setAuthServerOk] = useState<boolean | null>(null);

  const checkAuth = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setLoading(false);
      setAuthServerOk(null);
      return;
    }
    try {
      const u = await authApi<User>("/api/auth/me");
      setUser(u);
      setAuthServerOk(true);
    } catch {
      setAuthToken(null);
      setUser(null);
      setAuthServerOk(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi<{ token: string; user: User }>(
      "/api/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }
    );
    console.log("LOGIN RESPONSE:", JSON.stringify(data));
    setAuthToken(data.token);
    setUser(data.user ?? { id: 0, email, username: "", subscription: "free" });
    setAuthServerOk(true);
    setLoading(false);

    // Auto-sync positions with broker balance after login (all connected brokers)
    try {
      const accounts = await brokerApi.getConnectedAccounts();
      for (const acc of accounts) {
        api(`/api/broker/${acc.brokerId}/sync-positions`, { method: "POST" }).catch(() => {});
      }
    } catch {}

    return data.user;
  }, []);

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const data = await authApi<{ token: string; user: User }>(
        "/api/auth/register",
        {
          method: "POST",
          body: JSON.stringify({ email, username, password }),
        }
      );
      setAuthToken(data.token);
      setUser(data.user);
      setAuthServerOk(true);

      // Auto-sync positions with broker balance after register (all connected brokers)
      try {
        const accounts = await brokerApi.getConnectedAccounts();
        for (const acc of accounts) {
          api(`/api/broker/${acc.brokerId}/sync-positions`, { method: "POST" }).catch(() => {});
        }
      } catch {}

      return data.user;
    },
    []
  );

  const logout = useCallback(() => {
    setAuthToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    // Don't check auth on mount — always require login
    setLoading(false);
    const handler = () => {
      setUser(null);
      setLoading(false);
    };
    window.addEventListener("auth-logout", handler);
    return () => window.removeEventListener("auth-logout", handler);
  }, []);

  return {
    user,
    loading,
    authServerOk,
    login,
    register,
    logout,
    checkAuth,
  };
}
