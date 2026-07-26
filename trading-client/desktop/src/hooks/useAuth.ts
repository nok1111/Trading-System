import { useCallback, useEffect, useState } from "react";
import { authApi, getAuthToken, setAuthToken } from "../lib/api";

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
    setAuthToken(data.token);
    setUser(data.user);
    setAuthServerOk(true);
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
      return data.user;
    },
    []
  );

  const logout = useCallback(() => {
    setAuthToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    checkAuth();
    const handler = () => {
      setUser(null);
      setLoading(false);
    };
    window.addEventListener("auth-logout", handler);
    return () => window.removeEventListener("auth-logout", handler);
  }, [checkAuth]);

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
