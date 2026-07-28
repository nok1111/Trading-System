import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

/** Hook for live price updates via polling with short TTL cache.
 *
 * Uses the existing /api/prices/live endpoint. The API cache TTL for this
 * endpoint is 5 seconds, so switching tabs or re-mounting won't cause
 * duplicate requests within that window.
 */
export function useLivePrice(symbol: string | null): { price: number | null; loading: boolean } {
  const [price, setPrice] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    if (!symbol) {
      setPrice(null);
      setLoading(false);
      return;
    }

    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (!aliveRef.current) return;
      try {
        const data = await api<{ prices: Record<string, string> }>("/api/prices/live");
        if (!aliveRef.current) return;
        const raw = data?.prices?.[symbol];
        if (raw) {
          setPrice(parseFloat(raw));
          setLoading(false);
        }
      } catch {
        // ignore — will retry
      }
      if (aliveRef.current) {
        timer = setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      aliveRef.current = false;
      if (timer) clearTimeout(timer);
    };
  }, [symbol]);

  return { price, loading };
}

/** Hook for all live prices (for position tables, overview, etc.) */
export function useAllLivePrices(): { prices: Record<string, number>; loading: boolean } {
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (!aliveRef.current) return;
      try {
        const data = await api<{ prices: Record<string, string> }>("/api/prices/live");
        if (!aliveRef.current) return;
        const parsed: Record<string, number> = {};
        for (const [sym, val] of Object.entries(data?.prices ?? {})) {
          parsed[sym] = parseFloat(val);
        }
        setPrices(parsed);
        setLoading(false);
      } catch {
        // ignore
      }
      if (aliveRef.current) {
        timer = setTimeout(poll, 5000);
      }
    };

    poll();

    return () => {
      aliveRef.current = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return { prices, loading };
}
