import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CandlestickSeries, HistogramSeries, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { api } from "../../lib/api";

interface PriceChartProps {
  symbol: string;
  interval?: string;
  height?: number;
}

const INTERVALS = [
  { value: "1m", label: "1m" },
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1h" },
  { value: "4h", label: "4h" },
  { value: "1d", label: "1D" },
];

export function PriceChart({ symbol, interval: initialInterval = "1h", height = 400 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [interval, setIntervalState] = useState(initialInterval);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const root = document.documentElement;
    const cs = getComputedStyle(root);
    const cssVar = (name: string) => cs.getPropertyValue(name).trim() || "#333333";
    const cBorder = cssVar("--color-border");
    const cTextMuted = cssVar("--color-text-muted");
    const cSuccess = cssVar("--color-success");
    const cDanger = cssVar("--color-danger");
    const cSurface = cssVar("--color-surface");

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: cSurface },
        textColor: cTextMuted,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: cBorder },
        horzLines: { color: cBorder },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: cTextMuted, width: 1, style: 2 },
        horzLine: { color: cTextMuted, width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: cBorder,
      },
      timeScale: {
        borderColor: cBorder,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: cSuccess,
      downColor: cDanger,
      borderUpColor: cSuccess,
      borderDownColor: cDanger,
      wickUpColor: cSuccess,
      wickDownColor: cDanger,
    });
    seriesRef.current = candleSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volumeRef.current = volumeSeries;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || !volumeRef.current) return;
    let alive = true;
    setLoading(true);
    setError(null);

    const load = async () => {
      try {
        const data = await api<any[]>(`/api/klines/${symbol}?interval=${interval}&limit=300`);
        if (!alive) return;

        const root = document.documentElement;
        const cs = getComputedStyle(root);
        const hexToRgba = (hex: string, alpha: number) => {
          const h = hex.replace("#", "");
          const r = parseInt(h.substring(0, 2), 16);
          const g = parseInt(h.substring(2, 4), 16);
          const b = parseInt(h.substring(4, 6), 16);
          return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        };
        const volUp = hexToRgba(cs.getPropertyValue("--color-success").trim() || "#22d39a", 0.3);
        const volDown = hexToRgba(cs.getPropertyValue("--color-danger").trim() || "#ff5f6d", 0.3);

        const candles = data.map((k) => ({
          time: Math.floor(k.time / 1000) as any,
          open: Number(k.open),
          high: Number(k.high),
          low: Number(k.low),
          close: Number(k.close),
        }));

        const volumes = data.map((k) => ({
          time: Math.floor(k.time / 1000) as any,
          value: Number(k.volume),
          color: Number(k.close) >= Number(k.open) ? volUp : volDown,
        }));

        seriesRef.current!.setData(candles);
        volumeRef.current!.setData(volumes);
        chartRef.current!.timeScale().fitContent();
        setLoading(false);
      } catch (e: any) {
        if (alive) {
          setError(e.message || "Error al cargar datos");
          setLoading(false);
        }
      }
    };
    load();
    return () => { alive = false; };
  }, [symbol, interval]);

  return (
    <div className="panel p-4 relative">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">{symbol} · Chart</h3>
        <div className="flex gap-1">
          {INTERVALS.map((iv) => (
            <button
              key={iv.value}
              onClick={() => setIntervalState(iv.value)}
              className={`px-2 h-6 rounded-[6px] text-[11px] font-bold transition-colors ${
                interval === iv.value
                  ? "bg-[var(--color-primary)] text-white"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              }`}
            >
              {iv.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-[12px] text-[var(--color-danger)] py-4 text-center">{error}</div>
      )}

      {loading && !error && (
        <div className="flex items-center justify-center absolute inset-0 bg-[var(--color-surface)]/80 rounded-[12px] z-10" style={{ height }}>
          <div className="text-[12px] text-[var(--color-text-muted)]">Cargando {symbol}...</div>
        </div>
      )}

      <div ref={containerRef} style={{ height, visibility: error ? "hidden" : "visible" }} />
    </div>
  );
}
