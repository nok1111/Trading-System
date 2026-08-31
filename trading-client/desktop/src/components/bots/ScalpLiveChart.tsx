import { useCallback, useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries, type IChartApi, type ISeriesApi, type IPriceLine, type UTCTimestamp } from "lightweight-charts";
import { api } from "../../lib/api";

interface Marker {
  time: number;
  price: number;
  side: "buy" | "sell" | string;
  event: string;
}

interface Props {
  symbol: string | null;
  height?: number;
  markers?: Marker[];
}

export function ScalpLiveChart({ symbol, height = 260, markers = [] }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const linesRef = useRef<IPriceLine[]>([]);

  useEffect(() => {
    if (!wrapRef.current) return;
    const chart = createChart(wrapRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9aa4b2",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const ro = new ResizeObserver(() => {
      if (wrapRef.current) chart.applyOptions({ width: wrapRef.current.clientWidth });
    });
    ro.observe(wrapRef.current);
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  const lastBuy = [...markers].reverse().find((m) => m.event === "buy" || m.side === "long");
  const lastSell = [...markers].reverse().find((m) => m.event === "sell" || m.side === "short");

  const load = useCallback(async () => {
    if (!symbol || !seriesRef.current) return;
    try {
      const rows = await api<any[]>(`/api/bots/scalp/klines?symbol=${encodeURIComponent(symbol)}&interval=1m&limit=180`);
      if (!Array.isArray(rows) || !rows.length) return;
      seriesRef.current.setData(rows.map((k) => ({
        time: (Math.floor(Number(k.time) / 1000) as UTCTimestamp),
        open: Number(k.open),
        high: Number(k.high),
        low: Number(k.low),
        close: Number(k.close),
      })));
      for (const line of linesRef.current) {
        try { seriesRef.current.removePriceLine(line); } catch { /* */ }
      }
      linesRef.current = [];
      if (lastBuy?.price) {
        linesRef.current.push(seriesRef.current.createPriceLine({
          price: lastBuy.price, color: "#22c55e", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: "BUY",
        }));
      }
      if (lastSell?.price) {
        linesRef.current.push(seriesRef.current.createPriceLine({
          price: lastSell.price, color: "#ef4444", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: "SELL",
        }));
      }
      chartRef.current?.timeScale().fitContent();
    } catch {
      /* ignore */
    }
  }, [symbol, lastBuy?.price, lastSell?.price]);

  useEffect(() => {
    load();
    if (!symbol) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load, symbol]);

  if (!symbol) {
    return (
      <div className="h-[260px] flex items-center justify-center text-[11px] text-[var(--color-text-muted)]">
        Esperando símbolo del bot…
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)]">
        <span className="text-[11px] font-bold text-[var(--color-text)]">{symbol} · 1m futuros</span>
        <span className="text-[10px] text-[var(--color-text-muted)]">se actualiza al cambiar de par</span>
      </div>
      <div ref={wrapRef} />
    </div>
  );
}
