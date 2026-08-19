import { useState, useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "./useWebSocket";

interface DbPosition {
  id: number;
  symbol: string;
  side: string;
  quantity: string;
  entry_price: string | null;
  current_price: string | null;
  stop_loss: string | null;
  take_profit: string | null;
  unrealized_pnl: string | null;
  realized_pnl: string | null;
  status: string;
  auto_sell_enabled: boolean | null;
  broker_id: string | null;
  opened_at: string | null;
  closed_at: string | null;
  strategy_name: string;
  metadata_json: Record<string, any>;
}

interface UseDbPositionsReturn {
  positions: DbPosition[];
  loading: boolean;
  error: string | null;
  lastUpdate: number | null;
  closedIds: number[];
  refresh: () => void;
}

/**
 * Hook that subscribes to real-time DB position updates via WebSocket.
 *
 * Receives instant push notifications when positions change:
 * - Position closed (by user, AI agent, or auto-close loop)
 * - SL/TP updated
 * - Auto-sell toggled
 *
 * Falls back to REST polling every 5s if WS fails.
 */
export function useDbPositions(): UseDbPositionsReturn {
  const [positions, setPositions] = useState<DbPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [closedIds, setClosedIds] = useState<number[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastClosedRef = useRef<number[]>([]);

  const onMessage = useCallback((data: any) => {
    if (data.type === "snapshot" || data.type === "update") {
      if (data.positions) {
        setPositions(data.positions);
        setLastUpdate(Date.now());
      }
      if (data.closed_ids && data.closed_ids.length > 0) {
        setClosedIds(data.closed_ids);
        lastClosedRef.current = data.closed_ids;
      }
      setError(null);
      setLoading(false);
    } else if (data.type === "error") {
      setError(data.message || "Error fetching positions");
      setLoading(false);
    }
  }, []);

  // Connect WebSocket
  const { connected } = useWebSocket("/api/ws/db-positions", {
    onMessage,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  });

  const refresh = useCallback(async () => {
    try {
      const jwt = localStorage.getItem("jwt") || "";
      const base = import.meta.env.DEV
        ? "http://76.13.180.80:8080"
        : "";
      const resp = await fetch(`${base}/api/positions`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      if (!resp.ok) return;
      const data = await resp.json();
      if (Array.isArray(data)) {
        setPositions(data);
        setLastUpdate(Date.now());
      }
    } catch {
      // Silent
    }
  }, []);

  // Fallback: REST polling if WS is not connected
  useEffect(() => {
    if (connected) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    refresh();
    pollRef.current = setInterval(refresh, 5000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [connected, refresh]);

  return { positions, loading, error, lastUpdate, closedIds, refresh };
}
