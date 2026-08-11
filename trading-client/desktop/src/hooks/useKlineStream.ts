import { useState, useEffect, useCallback } from "react";
import { useWebSocket } from "./useWebSocket";

interface KlineUpdate {
  time: number;      // seconds (unix)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  isClosed: boolean; // true when the candle is finalized
}

interface UseKlineStreamReturn {
  lastKline: KlineUpdate | null;
  connected: boolean;
}

/**
 * Hook que conecta al WebSocket de klines de Binance (via backend proxy)
 * y recibe actualizaciones de la vela en formación en tiempo real.
 *
 * @param symbol   Ej: "BTCUSDT"
 * @param interval Ej: "1m", "5m", "15m", "1h", "4h", "1d"
 */
export function useKlineStream(symbol: string, interval: string): UseKlineStreamReturn {
  const [lastKline, setLastKline] = useState<KlineUpdate | null>(null);
  const [connected, setConnected] = useState(false);

  const path = `/api/ws/klines/${symbol}?interval=${interval}`;

  const onMessage = useCallback((data: any) => {
    if (data.type === "connected") {
      setConnected(true);
    } else if (data.type === "kline" && data.kline) {
      const k = data.kline;
      setLastKline({
        time: Math.floor(k.time / 1000),
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
        volume: k.volume,
        isClosed: k.is_closed,
      });
    } else if (data.type === "error") {
      setConnected(false);
    }
  }, []);

  const { connected: wsConnected } = useWebSocket(path, {
    onMessage,
    maxReconnectAttempts: 5,
  });

  // Sync connected state
  useEffect(() => {
    if (!wsConnected) setConnected(false);
  }, [wsConnected]);

  return { lastKline, connected };
}
