import { useState, useEffect, useCallback } from "react";
import { fetch as tauriFetch } from "../../lib/api";
import { useI18n } from "../../i18n/I18nContext";

interface OrderBookProps {
  brokerId: string;
  symbol: string;
}

interface OrderBookData {
  symbol: string;
  bids: [string, string][];
  asks: [string, string][];
  timestamp: number | null;
  spread: string | null;
}

export function OrderBook({ brokerId, symbol }: OrderBookProps) {
  const { t } = useI18n();
  const [data, setData] = useState<OrderBookData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [maxRows] = useState(12);

  const fetchOrderBook = useCallback(async () => {
    try {
      const token = localStorage.getItem("jwt") || "";
      const resp = await tauriFetch(
        `${import.meta.env.PROD ? "http://76.13.180.80:8080" : ""}/api/broker/${brokerId}/orderbook?symbol=${encodeURIComponent(symbol)}&depth=20`,
        { headers: { Authorization: `Bearer ${token}` } } as any
      );
      if (!resp.ok) throw new Error("Error fetching order book");
      const json = await resp.json();
      setData(json);
      setError(null);
      setLoading(false);
    } catch (e: any) {
      setError(e.message || "Error");
      setLoading(false);
    }
  }, [brokerId, symbol]);

  // Poll every 2 seconds
  useEffect(() => {
    fetchOrderBook();
    const interval = setInterval(fetchOrderBook, 2000);
    return () => clearInterval(interval);
  }, [fetchOrderBook]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[12px] text-[var(--color-text-muted)]">
        Cargando order book...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-[12px] text-[var(--color-danger)]">
        {error}
      </div>
    );
  }

  if (!data) return null;

  const bids = data.bids.slice(0, maxRows);
  const asks = data.asks.slice(0, maxRows).reverse(); // Reversed for display (best ask at bottom)

  // Calculate max volume for bar scaling
  const allVols = [...bids, ...asks].map(([, q]) => parseFloat(q));
  const maxVol = Math.max(...allVols, 0.0001);

  const spread = data.spread ? parseFloat(data.spread) : null;
  const bestBid = data.bids[0] ? parseFloat(data.bids[0][0]) : null;
  const bestAsk = data.asks[0] ? parseFloat(data.asks[0][0]) : null;
  const midPrice = bestBid && bestAsk ? (bestBid + bestAsk) / 2 : null;

  return (
    <div className="flex flex-col h-full text-[11px] font-mono">
      {/* Header */}
      <div className="flex items-center justify-between px-2 py-1.5 border-b border-[var(--color-border)]">
        <span className="font-bold text-[var(--color-text)]">{t("trading.orderBook")}</span>
        <span className="text-[var(--color-text-muted)]">{symbol}</span>
      </div>

      {/* Column headers */}
      <div className="flex px-2 py-1 text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">
        <span className="flex-1 text-right">Precio</span>
        <span className="flex-1 text-right">Cantidad</span>
        <span className="flex-1 text-right">Total</span>
      </div>

      {/* Asks (sells) - red, reversed so best ask is at bottom */}
      <div className="flex-1 overflow-y-auto">
        {asks.map(([price, qty], i) => {
          const vol = parseFloat(qty);
          const total = parseFloat(price) * vol;
          const barWidth = (vol / maxVol) * 100;
          return (
            <div key={`ask-${i}`} className="relative flex px-2 py-0.5 hover:bg-[var(--color-surface-hover)]">
              <div
                className="absolute right-0 top-0 bottom-0 bg-red-500/10"
                style={{ width: `${barWidth}%` }}
              />
              <span className="flex-1 text-right text-red-400 relative z-10">{parseFloat(price).toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
              <span className="flex-1 text-right text-[var(--color-text)] relative z-10">{vol.toFixed(6)}</span>
              <span className="flex-1 text-right text-[var(--color-text-muted)] relative z-10">{total.toFixed(2)}</span>
            </div>
          );
        })}
      </div>

      {/* Spread / mid price */}
      <div className="flex items-center justify-between px-2 py-1.5 border-y border-[var(--color-border)] bg-[var(--color-surface-2)]">
        {midPrice && (
          <span className="font-bold text-[13px] text-[var(--color-text)]">
            {midPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </span>
        )}
        {spread !== null && (
          <span className="text-[10px] text-[var(--color-text-muted)]">
            Spread: {spread.toFixed(4)}
          </span>
        )}
      </div>

      {/* Bids (buys) - green */}
      <div className="flex-1 overflow-y-auto">
        {bids.map(([price, qty], i) => {
          const vol = parseFloat(qty);
          const total = parseFloat(price) * vol;
          const barWidth = (vol / maxVol) * 100;
          return (
            <div key={`bid-${i}`} className="relative flex px-2 py-0.5 hover:bg-[var(--color-surface-hover)]">
              <div
                className="absolute right-0 top-0 bottom-0 bg-green-500/10"
                style={{ width: `${barWidth}%` }}
              />
              <span className="flex-1 text-right text-green-400 relative z-10">{parseFloat(price).toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
              <span className="flex-1 text-right text-[var(--color-text)] relative z-10">{vol.toFixed(6)}</span>
              <span className="flex-1 text-right text-[var(--color-text-muted)] relative z-10">{total.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
