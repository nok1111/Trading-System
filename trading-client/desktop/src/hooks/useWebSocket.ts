import { useEffect, useRef, useState, useCallback } from "react";

type MessageHandler = (data: any) => void;

interface UseWebSocketOptions {
  onMessage?: MessageHandler;
  onOpen?: () => void;
  onClose?: () => void;
  onAuthError?: () => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  connected: boolean;
  send: (msg: string | object) => void;
  reconnect: () => void;
}

/**
 * Hook para conectar a un WebSocket del backend.
 * Auto-reconecta con backoff exponencial.
 *
 * Token handling: reads JWT from localStorage on every connect/reconnect,
 * so refreshed tokens are picked up automatically. If the server closes
 * the connection with an auth error code (4001), the onAuthError callback
 * is invoked and a `ws-auth-error` event is dispatched.
 */
export function useWebSocket(
  path: string,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    onMessage,
    onOpen,
    onClose,
    onAuthError,
    reconnectInterval = 2000,
    maxReconnectAttempts = 10,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);

  // Keep refs to latest callbacks without re-creating the WS
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onAuthErrorRef = useRef(onAuthError);
  onMessageRef.current = onMessage;
  onOpenRef.current = onOpen;
  onCloseRef.current = onClose;
  onAuthErrorRef.current = onAuthError;

  const connect = useCallback(() => {
    // Read token FRESH from localStorage on every connect/reconnect
    // This ensures we pick up refreshed tokens after re-login
    const token = localStorage.getItem("jwt") || "";
    const separator = path.includes("?") ? "&" : "?";

    let url: string;
    // In production (Tauri), connect directly to the VPS backend
    // In dev mode (Vite), also connect directly (Vite proxy doesn't handle WS well)
    const isDev = window.location.port === "1420" || window.location.hostname === "localhost";
    if (isDev || import.meta.env.PROD) {
      // Connect directly to the VPS backend for WS
      url = `ws://76.13.180.80:8080${path}${separator}token=${encodeURIComponent(token)}`;
    } else {
      // Browser deployment: use same origin
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname;
      const port = window.location.port ? `:${window.location.port}` : "";
      url = `${protocol}//${host}${port}${path}${separator}token=${encodeURIComponent(token)}`;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttemptsRef.current = 0;
        onOpenRef.current?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessageRef.current?.(data);
        } catch {
          // Non-JSON message, ignore
        }
      };

      ws.onclose = (event) => {
        setConnected(false);
        onCloseRef.current?.();

        // Check for auth error close code (4001 = Unauthorized)
        if (event.code === 4001) {
          onAuthErrorRef.current?.();
          window.dispatchEvent(new CustomEvent("ws-auth-error", {
            detail: { code: event.code, reason: event.reason }
          }));
          // Don't auto-reconnect on auth errors — the app should handle re-login
          return;
        }

        // Auto-reconnect with backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const backoff = Math.min(
            reconnectInterval * (2 ** reconnectAttemptsRef.current),
            30000
          );
          reconnectAttemptsRef.current++;
          reconnectTimerRef.current = setTimeout(connect, backoff);
        }
      };

      ws.onerror = () => {
        // Error will trigger onclose which handles reconnection
      };
    } catch {
      // Connection failed, will retry
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const backoff = Math.min(
          reconnectInterval * (2 ** reconnectAttemptsRef.current),
          30000
        );
        reconnectAttemptsRef.current++;
        reconnectTimerRef.current = setTimeout(connect, backoff);
      }
    }
  }, [path, reconnectInterval, maxReconnectAttempts]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((msg: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const data = typeof msg === "string" ? msg : JSON.stringify(msg);
      wsRef.current.send(data);
    }
  }, []);

  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    // Re-read token on manual reconnect
    connect();
  }, [connect]);

  return { connected, send, reconnect };
}
