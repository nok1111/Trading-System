import { useEffect, useRef, useState, useCallback } from "react";
import { useKlineStream } from "../../hooks/useKlineStream";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
} from "lightweight-charts";
import { EMA, RSI, MACD, BollingerBands } from "technicalindicators";
import { api } from "../../lib/api";
import { cn } from "../../lib/utils";

interface PriceChartProps {
  symbol: string;
  interval?: string;
  height?: number;
  stopLoss?: number | null;
  takeProfit?: number | null;
  entryPrice?: number | null;
  brokerId?: string;
}

const INTERVALS = [
  { value: "1m", label: "1m" },
  { value: "5m", label: "5m" },
  { value: "15m", label: "15m" },
  { value: "1h", label: "1h" },
  { value: "4h", label: "4h" },
  { value: "1d", label: "1D" },
  { value: "1w", label: "1W" },
];

// Optimal candle count per timeframe — keeps data range sensible so the
// time axis doesn't have to compress 500 1m candles into a tiny space.
const LIMIT_BY_INTERVAL: Record<string, number> = {
  "1m": 180,    // 3 hours
  "5m": 288,    // 1 day
  "15m": 384,   // 4 days
  "30m": 480,   // 10 days
  "1h": 500,    // ~21 days
  "2h": 500,    // ~42 days
  "4h": 500,    // ~83 days
  "6h": 500,    // ~125 days
  "8h": 500,    // ~167 days
  "12h": 500,   // ~250 days
  "1d": 500,    // ~1.4 years
  "1w": 500,    // ~9.6 years
};

function makeTickFormatter(interval: string) {
  return (time: any, tickMarkType: number, locale: string): string => {
    const ts = typeof time === "number" ? time : Number(time);
    const d = new Date(ts * 1000);
    const isMinuteTf = interval === "1m" || interval === "5m" || interval === "15m" || interval === "30m";
    const isHourlyTf = interval === "1h" || interval === "2h" || interval === "4h" || interval === "6h" || interval === "8h" || interval === "12h";

    // tickMarkType: 0=Year, 1=Month, 2=DayOfMonth, 3=Time, 4=TimeWithSeconds
    if (tickMarkType === 0) return d.getFullYear().toString();
    if (tickMarkType === 1) return d.toLocaleDateString(locale, { month: "short", year: "2-digit" });
    if (tickMarkType === 2) {
      // Day boundary — for intraday show day+month, for daily+ show just day
      if (isMinuteTf || isHourlyTf) {
        return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
      }
      return d.toLocaleDateString(locale, { day: "numeric", month: "short" });
    }
    // tickMarkType 3 or 4 — Time (intraday ticks)
    if (isMinuteTf) {
      // 1m/5m/15m: show HH:MM
      return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    }
    if (isHourlyTf) {
      // 1h/4h: show HH:MM
      return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    }
    // Daily/weekly: show date
    return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
  };
}

interface IndicatorState {
  ema: boolean;
  emaPeriod: number;
  ema2: boolean;
  ema2Period: number;
  bollinger: boolean;
  bbPeriod: number;
  bbStdDev: number;
  volume: boolean;
  rsi: boolean;
  rsiPeriod: number;
  macd: boolean;
}

const DEFAULT_INDICATORS: IndicatorState = {
  ema: true,
  emaPeriod: 20,
  ema2: true,
  ema2Period: 50,
  bollinger: false,
  bbPeriod: 20,
  bbStdDev: 2,
  volume: true,
  rsi: false,
  rsiPeriod: 14,
  macd: false,
};

export function PriceChart({ symbol, interval: initialInterval = "1h", height = 400, stopLoss, takeProfit, entryPrice, brokerId }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);
  const macdContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const emaRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema2Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMidRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdChartRef = useRef<IChartApi | null>(null);
  const macdSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [interval, setIntervalState] = useState(initialInterval);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [indicators, setIndicators] = useState<IndicatorState>(DEFAULT_INDICATORS);
  const [showSettings, setShowSettings] = useState(false);

  // Drawing tools state
  const [drawMode, setDrawMode] = useState(false);
  const [userLines, setUserLines] = useState<number[]>([]);
  const userLineRefs = useRef<IPriceLine[]>([]);

  const slLineRef = useRef<IPriceLine | null>(null);
  const tpLineRef = useRef<IPriceLine | null>(null);
  const entryLineRef = useRef<IPriceLine | null>(null);

  // Load saved drawing lines from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(`chart_lines_${symbol}`);
    if (saved) {
      try {
        const lines = JSON.parse(saved) as number[];
        setUserLines(lines);
      } catch { /* ignore */ }
    } else {
      setUserLines([]);
    }
  }, [symbol]);

  // Save drawing lines to localStorage
  useEffect(() => {
    if (userLines.length > 0) {
      localStorage.setItem(`chart_lines_${symbol}`, JSON.stringify(userLines));
    } else {
      localStorage.removeItem(`chart_lines_${symbol}`);
    }
  }, [userLines, symbol]);

  // Apply/remove user lines on the chart
  useEffect(() => {
    if (!seriesRef.current) return;

    // Remove old lines
    userLineRefs.current.forEach((line) => seriesRef.current?.removePriceLine(line));
    userLineRefs.current = [];

    // Add new lines
    userLines.forEach((price) => {
      const line = seriesRef.current!.createPriceLine({
        price,
        color: "rgba(100, 149, 237, 0.6)",
        lineWidth: 1,
        lineStyle: 2, // dashed
        axisLabelVisible: true,
        title: "",
      });
      userLineRefs.current.push(line);
    });
  }, [userLines]);

  // Helper: get CSS vars
  const getCssVars = useCallback(() => {
    const root = document.documentElement;
    const cs = getComputedStyle(root);
    const get = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
    return {
      border: get("--color-border", "#333333"),
      textMuted: get("--color-text-muted", "#888888"),
      success: get("--color-success", "#22d39a"),
      danger: get("--color-danger", "#ff5f6d"),
      surface: get("--color-surface", "#1a1a2e"),
      primary: get("--color-primary", "#7c3aed"),
      warning: get("--color-warning", "#f59e0b"),
    };
  }, []);

  // ─── Main chart creation ───────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const c = getCssVars();

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: c.surface },
        textColor: c.textMuted,
        fontSize: 11,
        fontFamily: "system-ui, -apple-system, sans-serif",
      },
      grid: {
        vertLines: { color: c.border, style: 1 },
        horzLines: { color: c.border, style: 1 },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: c.textMuted, width: 1, style: 2, labelBackgroundColor: c.primary },
        horzLine: { color: c.textMuted, width: 1, style: 2, labelBackgroundColor: c.primary },
      },
      rightPriceScale: {
        borderColor: c.border,
        scaleMargins: { top: 0.05, bottom: indicators.volume ? 0.25 : 0.05 },
      },
      timeScale: {
        borderColor: c.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        tickMarkFormatter: makeTickFormatter(interval),
      } as any,
    });

    chartRef.current = chart;

    // Click handler for drawing mode — add horizontal line at clicked price
    chart.subscribeClick((param) => {
      if (!drawMode || !param.time || !seriesRef.current) return;
      const price = (param.point as any)?.price;
      if (price != null && price > 0) {
        setUserLines((prev) => [...prev, price]);
      }
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: c.success,
      downColor: c.danger,
      borderUpColor: c.success,
      borderDownColor: c.danger,
      wickUpColor: c.success,
      wickDownColor: c.danger,
      priceFormat: { type: "price", precision: 8, minMove: 0.00000001 },
      priceLineVisible: true,
      lastValueVisible: true,
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

    // EMA lines
    const emaSeries = chart.addSeries(LineSeries, {
      color: c.warning,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    emaRef.current = emaSeries;

    const ema2Series = chart.addSeries(LineSeries, {
      color: c.primary,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema2Ref.current = ema2Series;

    // Bollinger Bands
    const bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(124, 58, 237, 0.5)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      lineStyle: 2,
    });
    bbUpperRef.current = bbUpper;

    const bbMid = chart.addSeries(LineSeries, {
      color: "rgba(124, 58, 237, 0.3)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      lineStyle: 1,
    });
    bbMidRef.current = bbMid;

    const bbLower = chart.addSeries(LineSeries, {
      color: "rgba(124, 58, 237, 0.5)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      lineStyle: 2,
    });
    bbLowerRef.current = bbLower;

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
      seriesRef.current = null;
      volumeRef.current = null;
      emaRef.current = null;
      ema2Ref.current = null;
      bbUpperRef.current = null;
      bbMidRef.current = null;
      bbLowerRef.current = null;
    };
  }, [height]);

  // ─── Update tickMarkFormatter when interval changes ────────────────────────
  useEffect(() => {
    if (!chartRef.current) return;
    (chartRef.current.timeScale().applyOptions as any)({
      tickMarkFormatter: makeTickFormatter(interval),
    });
  }, [interval]);

  // ─── RSI sub-chart ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!indicators.rsi || !rsiContainerRef.current) {
      if (rsiChartRef.current) {
        rsiChartRef.current.remove();
        rsiChartRef.current = null;
        rsiSeriesRef.current = null;
      }
      return;
    }
    const c = getCssVars();
    const rsiChart = createChart(rsiContainerRef.current, {
      width: rsiContainerRef.current.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: c.surface },
        textColor: c.textMuted,
        fontSize: 10,
      },
      grid: {
        vertLines: { color: c.border, style: 1 },
        horzLines: { color: c.border, style: 1 },
      },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: true, secondsVisible: false, tickMarkFormatter: makeTickFormatter(interval) } as any,
    });
    rsiChartRef.current = rsiChart;

    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: c.warning,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });
    rsiSeriesRef.current = rsiSeries;

    // Overbought/oversold lines
    rsiSeries.createPriceLine({ price: 70, color: c.danger, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "OB" });
    rsiSeries.createPriceLine({ price: 30, color: c.success, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "OS" });
    rsiSeries.createPriceLine({ price: 50, color: c.textMuted, lineWidth: 1, lineStyle: 1, axisLabelVisible: false });

    // Sync time scale with main chart
    if (chartRef.current) {
      chartRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range && rsiChartRef.current) {
          rsiChartRef.current.timeScale().setVisibleLogicalRange(range);
        }
      });
    }

    const handleResize = () => {
      if (rsiContainerRef.current && rsiChartRef.current) {
        rsiChartRef.current.applyOptions({ width: rsiContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      rsiChart.remove();
      rsiChartRef.current = null;
      rsiSeriesRef.current = null;
    };
  }, [indicators.rsi]);

  // ─── MACD sub-chart ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!indicators.macd || !macdContainerRef.current) {
      if (macdChartRef.current) {
        macdChartRef.current.remove();
        macdChartRef.current = null;
        macdSeriesRef.current = null;
        macdSignalRef.current = null;
        macdHistRef.current = null;
      }
      return;
    }
    const c = getCssVars();
    const macdChart = createChart(macdContainerRef.current, {
      width: macdContainerRef.current.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: c.surface },
        textColor: c.textMuted,
        fontSize: 10,
      },
      grid: {
        vertLines: { color: c.border, style: 1 },
        horzLines: { color: c.border, style: 1 },
      },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: true, secondsVisible: false, tickMarkFormatter: makeTickFormatter(interval) } as any,
    });
    macdChartRef.current = macdChart;

    const macdSeries = macdChart.addSeries(LineSeries, {
      color: c.primary,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });
    macdSeriesRef.current = macdSeries;

    const macdSignal = macdChart.addSeries(LineSeries, {
      color: c.warning,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    macdSignalRef.current = macdSignal;

    const macdHist = macdChart.addSeries(HistogramSeries, {
      priceFormat: { type: "price", precision: 6, minMove: 0.000001 },
    });
    macdHistRef.current = macdHist;

    // Sync with main chart
    if (chartRef.current) {
      chartRef.current.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range && macdChartRef.current) {
          macdChartRef.current.timeScale().setVisibleLogicalRange(range);
        }
      });
    }

    const handleResize = () => {
      if (macdContainerRef.current && macdChartRef.current) {
        macdChartRef.current.applyOptions({ width: macdContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      macdChart.remove();
      macdChartRef.current = null;
      macdSeriesRef.current = null;
      macdSignalRef.current = null;
      macdHistRef.current = null;
    };
  }, [indicators.macd]);

  // ─── Load data & compute indicators ────────────────────────────────────────
  useEffect(() => {
    if (!seriesRef.current || !volumeRef.current) return;
    let alive = true;
    setLoading(true);
    setError(null);

    const load = async () => {
      try {
        const limit = LIMIT_BY_INTERVAL[interval] || 500;
        const data = brokerId
          ? await api<any[]>(`/api/broker/${brokerId}/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`)
          : await api<any[]>(`/api/klines/${symbol}?interval=${interval}&limit=${limit}`);
        if (!alive || !data || data.length === 0) {
          if (alive) { setError("Sin datos para " + symbol); setLoading(false); }
          return;
        }

        const root = document.documentElement;
        const cs = getComputedStyle(root);
        const hexToRgba = (hex: string, alpha: number) => {
          const h = hex.replace("#", "").padStart(6, "0");
          const r = parseInt(h.substring(0, 2), 16);
          const g = parseInt(h.substring(2, 4), 16);
          const b = parseInt(h.substring(4, 6), 16);
          return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        };
        const volUp = hexToRgba(cs.getPropertyValue("--color-success").trim() || "#22d39a", 0.4);
        const volDown = hexToRgba(cs.getPropertyValue("--color-danger").trim() || "#ff5f6d", 0.4);

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

        // ─── Compute & set EMA ──────────────────────────────────────────────
        const closes = candles.map((c) => c.close);

        if (indicators.ema && emaRef.current && candles.length >= indicators.emaPeriod) {
          const emaVals = EMA.calculate({ period: indicators.emaPeriod, values: closes });
          const offset = candles.length - emaVals.length;
          const emaData = emaVals.map((v, i) => ({ time: candles[i + offset].time, value: v }));
          emaRef.current.setData(emaData);
        } else if (emaRef.current) {
          emaRef.current.setData([]);
        }

        if (indicators.ema2 && ema2Ref.current && candles.length >= indicators.ema2Period) {
          const ema2Vals = EMA.calculate({ period: indicators.ema2Period, values: closes });
          const offset = candles.length - ema2Vals.length;
          const ema2Data = ema2Vals.map((v, i) => ({ time: candles[i + offset].time, value: v }));
          ema2Ref.current.setData(ema2Data);
        } else if (ema2Ref.current) {
          ema2Ref.current.setData([]);
        }

        // ─── Bollinger Bands ────────────────────────────────────────────────
        if (indicators.bollinger && bbUpperRef.current && bbMidRef.current && bbLowerRef.current && candles.length >= indicators.bbPeriod) {
          const bb = BollingerBands.calculate({
            period: indicators.bbPeriod,
            stdDev: indicators.bbStdDev,
            values: closes,
          });
          const offset = candles.length - bb.length;
          const bbUpperData = bb.map((b, i) => ({ time: candles[i + offset].time, value: b.upper }));
          const bbMidData = bb.map((b, i) => ({ time: candles[i + offset].time, value: b.middle }));
          const bbLowerData = bb.map((b, i) => ({ time: candles[i + offset].time, value: b.lower }));
          bbUpperRef.current.setData(bbUpperData);
          bbMidRef.current.setData(bbMidData);
          bbLowerRef.current.setData(bbLowerData);
        } else {
          if (bbUpperRef.current) bbUpperRef.current.setData([]);
          if (bbMidRef.current) bbMidRef.current.setData([]);
          if (bbLowerRef.current) bbLowerRef.current.setData([]);
        }

        // ─── RSI ────────────────────────────────────────────────────────────
        if (indicators.rsi && rsiSeriesRef.current && candles.length >= indicators.rsiPeriod) {
          const rsiVals = RSI.calculate({ period: indicators.rsiPeriod, values: closes });
          const offset = candles.length - rsiVals.length;
          const rsiData = rsiVals.map((v, i) => ({ time: candles[i + offset].time, value: v }));
          rsiSeriesRef.current.setData(rsiData);
          rsiChartRef.current?.timeScale().fitContent();
        }

        // ─── MACD ───────────────────────────────────────────────────────────
        if (indicators.macd && macdSeriesRef.current && macdSignalRef.current && macdHistRef.current) {
          const macdVals = MACD.calculate({
            fastPeriod: 12,
            slowPeriod: 26,
            signalPeriod: 9,
            values: closes,
            SimpleMAOscillator: false,
            SimpleMASignal: false,
          } as any);
          const offset = candles.length - macdVals.length;
          const macdData = macdVals.map((m, i) => ({ time: candles[i + offset].time, value: m.MACD }));
          const signalData = macdVals.map((m, i) => ({ time: candles[i + offset].time, value: m.signal }));
          const histData = macdVals.map((m, i) => ({
            time: candles[i + offset].time,
            value: m.histogram,
            color: (m.histogram ?? 0) >= 0 ? volUp : volDown,
          }));
          macdSeriesRef.current.setData(macdData);
          macdSignalRef.current.setData(signalData);
          macdHistRef.current.setData(histData);
          macdChartRef.current?.timeScale().fitContent();
        }

        // Set price scale range
        if (chartRef.current && seriesRef.current) {
          const dataMin = Math.min(...candles.map((c) => c.low));
          const dataMax = Math.max(...candles.map((c) => c.high));
          const allPrices = [dataMin, dataMax];
          if (stopLoss != null && stopLoss > 0) allPrices.push(stopLoss);
          if (takeProfit != null && takeProfit > 0) allPrices.push(takeProfit);
          if (entryPrice != null && entryPrice > 0) allPrices.push(entryPrice);
          const minPrice = Math.min(...allPrices);
          const maxPrice = Math.max(...allPrices);
          const range = maxPrice - minPrice;
          const padding = range * 0.1;
          const ps = seriesRef.current.priceScale();
          ps.setAutoScale(false);
          ps.setVisibleRange({ from: minPrice - padding, to: maxPrice + padding });
        }

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
  }, [symbol, interval, brokerId, indicators]);

  // ─── Real-time kline updates via WebSocket ─────────────────────────────────
  const { lastKline } = useKlineStream(symbol, interval);

  useEffect(() => {
    if (!lastKline || !seriesRef.current || !volumeRef.current) return;

    // Update the last candle (or add a new one if the candle closed)
    const candleData = {
      time: lastKline.time as any,
      open: lastKline.open,
      high: lastKline.high,
      low: lastKline.low,
      close: lastKline.close,
    };
    const volumeData = {
      time: lastKline.time as any,
      value: lastKline.volume,
      color: lastKline.close >= lastKline.open
        ? "rgba(34, 211, 154, 0.4)"
        : "rgba(255, 95, 109, 0.4)",
    };

    try {
      seriesRef.current.update(candleData);
      volumeRef.current.update(volumeData);
    } catch {
      // update can fail if the time is before the last data point
    }
  }, [lastKline]);

  // ─── Draw SL/TP/entry price lines ──────────────────────────────────────────
  const drawPriceLines = useCallback(() => {
    const series = seriesRef.current;
    if (!series) return;

    if (slLineRef.current) { try { series.removePriceLine(slLineRef.current); } catch {} slLineRef.current = null; }
    if (tpLineRef.current) { try { series.removePriceLine(tpLineRef.current); } catch {} tpLineRef.current = null; }
    if (entryLineRef.current) { try { series.removePriceLine(entryLineRef.current); } catch {} entryLineRef.current = null; }

    if (stopLoss != null && stopLoss > 0) {
      slLineRef.current = series.createPriceLine({
        price: stopLoss,
        color: "#ff5f6d",
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `SL`,
      });
    }
    if (takeProfit != null && takeProfit > 0) {
      tpLineRef.current = series.createPriceLine({
        price: takeProfit,
        color: "#22d39a",
        lineWidth: 3,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `TP`,
        axisLabelColor: "#22d39a",
      });
    }
    if (entryPrice != null && entryPrice > 0) {
      entryLineRef.current = series.createPriceLine({
        price: entryPrice,
        color: "#888888",
        lineWidth: 1,
        lineStyle: 1,
        axisLabelVisible: true,
        title: `Entry`,
      });
    }
  }, [stopLoss, takeProfit, entryPrice]);

  useEffect(() => { drawPriceLines(); }, [drawPriceLines]);
  useEffect(() => {
    if (!loading) {
      const timer = setTimeout(drawPriceLines, 50);
      return () => clearTimeout(timer);
    }
  }, [loading, drawPriceLines]);

  // ─── Toggle indicator visibility ───────────────────────────────────────────
  useEffect(() => {
    if (emaRef.current) emaRef.current.applyOptions({ visible: indicators.ema });
    if (ema2Ref.current) ema2Ref.current.applyOptions({ visible: indicators.ema2 });
    if (volumeRef.current) volumeRef.current.applyOptions({ visible: indicators.volume });
    if (bbUpperRef.current) bbUpperRef.current.applyOptions({ visible: indicators.bollinger });
    if (bbMidRef.current) bbMidRef.current.applyOptions({ visible: indicators.bollinger });
    if (bbLowerRef.current) bbLowerRef.current.applyOptions({ visible: indicators.bollinger });
  }, [indicators.ema, indicators.ema2, indicators.volume, indicators.bollinger]);

  const toggleIndicator = (key: keyof IndicatorState) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="panel p-4 relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h3 className="text-[13px] font-bold text-[var(--color-text)]">{symbol}</h3>
          {entryPrice != null && (
            <span className="text-[10px] text-[var(--color-text-muted)]">Entry: ${entryPrice}</span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Interval selector */}
          <div className="flex gap-0.5 rounded-[8px] bg-[var(--color-surface-2)] p-0.5">
            {INTERVALS.map((iv) => (
              <button
                key={iv.value}
                onClick={() => setIntervalState(iv.value)}
                className={cn(
                  "px-2 h-6 rounded-[6px] text-[10px] font-bold transition-colors",
                  interval === iv.value
                    ? "bg-[var(--color-primary)] text-white"
                    : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
                )}
              >
                {iv.label}
              </button>
            ))}
          </div>

          {/* Indicator toggles */}
          <div className="flex gap-0.5 rounded-[8px] bg-[var(--color-surface-2)] p-0.5">
            <IndButton active={indicators.ema} onClick={() => toggleIndicator("ema")} color="var(--color-warning)" label="EMA20" />
            <IndButton active={indicators.ema2} onClick={() => toggleIndicator("ema2")} color="var(--color-primary)" label="EMA50" />
            <IndButton active={indicators.bollinger} onClick={() => toggleIndicator("bollinger")} color="#7c3aed" label="BB" />
            <IndButton active={indicators.volume} onClick={() => toggleIndicator("volume")} color="var(--color-text-muted)" label="VOL" />
            <IndButton active={indicators.rsi} onClick={() => toggleIndicator("rsi")} color="var(--color-warning)" label="RSI" />
            <IndButton active={indicators.macd} onClick={() => toggleIndicator("macd")} color="var(--color-primary)" label="MACD" />
          </div>

          {/* Drawing tools */}
          <div className="flex gap-0.5 rounded-[8px] bg-[var(--color-surface-2)] p-0.5">
            <button
              onClick={() => setDrawMode(!drawMode)}
              className={cn(
                "px-2 h-6 rounded-[6px] text-[10px] font-bold transition-colors flex items-center gap-1",
                drawMode
                  ? "bg-blue-500 text-white"
                  : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              )}
              title="Modo dibujo: click en chart para añadir línea horizontal"
            >
              {drawMode ? "Click chart →" : "Línea"}
            </button>
            {userLines.length > 0 && (
              <button
                onClick={() => setUserLines([])}
                className="px-2 h-6 rounded-[6px] text-[10px] font-bold text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 transition-colors"
                title="Borrar todas las líneas"
              >
                Borrar
              </button>
            )}
          </div>

          {/* Settings */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="px-2 h-6 rounded-[6px] text-[10px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            ⚙
          </button>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="mb-3 p-3 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] grid grid-cols-3 gap-3">
          <div>
            <label className="text-[9px] font-bold text-[var(--color-warning)] uppercase">EMA 1 Period</label>
            <input
              type="number" min={2} max={200} value={indicators.emaPeriod}
              onChange={(e) => setIndicators({ ...indicators, emaPeriod: parseInt(e.target.value) || 20 })}
              className="w-full h-7 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="text-[9px] font-bold text-[var(--color-primary)] uppercase">EMA 2 Period</label>
            <input
              type="number" min={2} max={200} value={indicators.ema2Period}
              onChange={(e) => setIndicators({ ...indicators, ema2Period: parseInt(e.target.value) || 50 })}
              className="w-full h-7 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">RSI Period</label>
            <input
              type="number" min={2} max={50} value={indicators.rsiPeriod}
              onChange={(e) => setIndicators({ ...indicators, rsiPeriod: parseInt(e.target.value) || 14 })}
              className="w-full h-7 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="text-[9px] font-bold text-[#7c3aed] uppercase">BB Period</label>
            <input
              type="number" min={5} max={100} value={indicators.bbPeriod}
              onChange={(e) => setIndicators({ ...indicators, bbPeriod: parseInt(e.target.value) || 20 })}
              className="w-full h-7 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)]"
            />
          </div>
          <div>
            <label className="text-[9px] font-bold text-[#7c3aed] uppercase">BB Std Dev</label>
            <input
              type="number" min={1} max={4} step={0.5} value={indicators.bbStdDev}
              onChange={(e) => setIndicators({ ...indicators, bbStdDev: parseFloat(e.target.value) || 2 })}
              className="w-full h-7 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)]"
            />
          </div>
        </div>
      )}

      {/* Chart area */}
      {error && (
        <div className="text-[12px] text-[var(--color-danger)] py-4 text-center">{error}</div>
      )}

      {loading && !error && (
        <div className="flex items-center justify-center absolute inset-0 bg-[var(--color-surface)]/80 rounded-[12px] z-10" style={{ height }}>
          <div className="text-[12px] text-[var(--color-text-muted)]">Cargando {symbol}...</div>
        </div>
      )}

      {/* Main candlestick chart */}
      <div ref={containerRef} style={{ height, visibility: error ? "hidden" : "visible" }} />

      {/* RSI sub-chart */}
      {indicators.rsi && !error && (
        <div className="mt-1">
          <div className="text-[9px] font-bold text-[var(--color-warning)] uppercase mb-0.5 px-1">RSI ({indicators.rsiPeriod})</div>
          <div ref={rsiContainerRef} style={{ height: 120 }} />
        </div>
      )}

      {/* MACD sub-chart */}
      {indicators.macd && !error && (
        <div className="mt-1">
          <div className="text-[9px] font-bold text-[var(--color-primary)] uppercase mb-0.5 px-1">MACD (12, 26, 9)</div>
          <div ref={macdContainerRef} style={{ height: 120 }} />
        </div>
      )}
    </div>
  );
}

// ─── Indicator toggle button ─────────────────────────────────────────────────
function IndButton({ active, onClick, color, label }: { active: boolean; onClick: () => void; color: string; label: string }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-1.5 h-6 rounded-[6px] text-[10px] font-bold transition-all flex items-center gap-1",
        active ? "text-white" : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
      )}
      style={active ? { backgroundColor: color } : {}}
    >
      {active && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
      {label}
    </button>
  );
}
