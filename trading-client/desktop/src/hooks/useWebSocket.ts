import { useEffect, useRef, useState, useCallback } from "react";

type MessageHandler = (data: any) => void;

interface UseWebSocketOptions {
  onMessage?: MessageHandler;
  onOpen?: () => void;
  onClose?: () => void;
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
 */
export function useWebSocket(
  path: string,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    onMessage,
    onOpen,
    onClose,
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
  onMessageRef.current = onMessage;
  onOpenRef.current = onOpen;
  onCloseRef.current = onClose;

  const connect = useCallback(() => {
    // Build WebSocket URL — in dev mode (Vite), the proxy doesn't forward
    // WS connections reliably, so connect directly to the backend VPS.
    // In production (Tauri), use window.location (same origin).
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

      ws.onclose = () => {
        setConnected(false);
        onCloseRef.current?.();

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
    connect();
  }, [connect]);

  return { connected, send, reconnect };
}
