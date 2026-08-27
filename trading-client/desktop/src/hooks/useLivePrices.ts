import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { fetch as tauriFetch } from "../lib/api";

interface LivePricesState {
  prices: Record<string, number>;
  connected: boolean;
  lastUpdate: number;
}

/**
 * Hook que mantiene precios en tiempo real via WebSocket.
 * Hace fallback a polling REST si el WS no está disponible.
 *
 * @param symbols Lista de símbolos a vigilar (ej: ["BTCUSDT", "ETHUSDT"])
 * @param fallbackInterval Ms entre polling de fallback (default: 10000)
 */
export function useLivePrices(
  symbols: string[] = [],
  fallbackInterval = 10000
): LivePricesState {
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [lastUpdate, setLastUpdate] = useState(0);
  const pricesRef = useRef<Record<string, number>>({});
  const symbolsKey = symbols.join(",");

  const onMessage = useCallback((data: any) => {
    if (data.type === "snapshot" && data.prices) {
      const newPrices: Record<string, number> = {};
      for (const [sym, price] of Object.entries(data.prices)) {
        newPrices[sym] = parseFloat(price as string);
      }
      pricesRef.current = { ...pricesRef.current, ...newPrices };
      setPrices({ ...pricesRef.current });
      setLastUpdate(Date.now());
    } else if (data.type === "tick" && data.symbol && data.price) {
      pricesRef.current[data.symbol] = parseFloat(data.price);
      setPrices({ ...pricesRef.current });
      setLastUpdate(Date.now());
    }
  }, []);

  const { connected } = useWebSocket("/api/ws/prices", { onMessage });

  // Fallback: poll REST endpoint if WS is not connected
  useEffect(() => {
    if (connected) return; // WS is working, no need to poll

    const poll = async () => {
      try {
        const resp = await tauriFetch("/api/prices/live" as any);
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.prices) {
          const newPrices: Record<string, number> = {};
          for (const [sym, price] of Object.entries(data.prices)) {
            newPrices[sym] = parseFloat(price as string);
          }
          pricesRef.current = { ...pricesRef.current, ...newPrices };
          setPrices({ ...pricesRef.current });
          setLastUpdate(Date.now());
        }
      } catch {
        // ignore
      }
    };

    poll();
    const id = setInterval(poll, fallbackInterval);
    return () => clearInterval(id);
  }, [connected, fallbackInterval, symbolsKey]);

  return { prices, connected, lastUpdate };
}

/**
 * Hook para obtener el precio de un solo símbolo en tiempo real.
 */
export function useLivePrice(symbol: string): {
  price: number | null;
  connected: boolean;
} {
  const { prices, connected } = useLivePrices([symbol]);
  return { price: prices[symbol] ?? null, connected };
}
