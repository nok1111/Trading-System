import { useState, useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "./useWebSocket";

interface LiveOrder {
  broker_order_id: string;
  symbol: string;
  side: string;
  type: string;
  quantity: string;
  price: string | null;
  status: string;
}

interface UseLiveOrdersReturn {
  orders: LiveOrder[];
  loading: boolean;
  error: string | null;
  lastUpdate: number | null;
}

/**
 * Hook that subscribes to real-time open orders updates via WebSocket.
 * Falls back to REST polling every 15s if WS fails.
 */
export function useLiveOrders(brokerId: string | null): UseLiveOrdersReturn {
  const [orders, setOrders] = useState<LiveOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const onMessage = useCallback((data: any) => {
    if (data.type === "snapshot" || data.type === "update") {
      if (data.orders) {
        setOrders(data.orders);
        setLastUpdate(Date.now());
      }
      setError(null);
      setLoading(false);
    } else if (data.type === "error") {
      setError(data.message || "Error fetching orders");
      setLoading(false);
    }
  }, []);

  const wsPath = brokerId ? `/api/ws/orders/${brokerId}` : null;
  const { connected } = useWebSocket(wsPath || "", {
    onMessage,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
  });

  // Fallback: REST polling if WS is not connected
  useEffect(() => {
    if (!brokerId) return;

    if (connected) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    const poll = async () => {
      try {
        const resp = await fetch(`/api/broker/${brokerId}/orders`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("jwt") || ""}`,
          },
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.active) {
          setOrders(data.active);
          setLastUpdate(Date.now());
        }
        setError(null);
        setLoading(false);
      } catch {
        // Silent
      }
    };

    poll();
    pollRef.current = setInterval(poll, 15000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [brokerId, connected]);

  return { orders, loading, error, lastUpdate };
}
