import { useState, useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "./useWebSocket";

interface LivePosition {
  symbol: string;
  side: string;
  quantity: string;
  entry_price: string | null;
  current_price: string | null;
  unrealized_pnl: string | null;
  leverage: number | null;
  liquidation_price: string | null;
}

interface UseLivePositionsReturn {
  positions: LivePosition[];
  loading: boolean;
  error: string | null;
  lastUpdate: number | null;
}

/**
 * Hook that subscribes to real-time position updates via WebSocket.
 * Falls back to REST polling every 15s if WS fails.
 */
export function useLivePositions(brokerId: string | null): UseLivePositionsReturn {
  const [positions, setPositions] = useState<LivePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const onMessage = useCallback((data: any) => {
    if (data.type === "snapshot" || data.type === "update") {
      if (data.positions) {
        setPositions(data.positions);
        setLastUpdate(Date.now());
      }
      setError(null);
      setLoading(false);
    } else if (data.type === "error") {
      setError(data.message || "Error fetching positions");
      setLoading(false);
    }
  }, []);

  // Connect WebSocket when brokerId is available
  const wsPath = brokerId ? `/api/ws/positions/${brokerId}` : null;
  const { connected } = useWebSocket(wsPath || "", {
    onMessage,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
  });

  // Fallback: REST polling if WS is not connected
  useEffect(() => {
    if (!brokerId) return;

    if (connected) {
      // WS is connected, clear any polling
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    // WS not connected, start REST polling fallback
    const poll = async () => {
      try {
        const resp = await fetch(`/api/broker/${brokerId}/positions`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("jwt") || ""}`,
          },
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.positions) {
          setPositions(data.positions);
          setLastUpdate(Date.now());
        }
        setError(null);
        setLoading(false);
      } catch {
        // Silent — WS will retry
      }
    };

    poll(); // Initial fetch
    pollRef.current = setInterval(poll, 15000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [brokerId, connected]);

  return { positions, loading, error, lastUpdate };
}
