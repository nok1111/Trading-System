import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "../lib/api";
import { fmt } from "../lib/utils";
import {
  ComposedChart,
  Line,
  Area,
  AreaChart,
  Bar,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  YAxis,
  XAxis,
  Tooltip,
  Scatter,
  ScatterChart,
  ZAxis,
} from "recharts";

export type ChartType =
  | "line"
  | "bar"
  | "candle"
  | "volume"
  | "ticks"
  | "range"
  | "pnf"
  | "renko"
  | "kagi"
  | "tlb";

interface Kline {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface PositionChartProps {
  symbol: string;
  entry: number;
  stopLoss: number;
  takeProfit: number;
  side: string;
  height?: number;
}

const CHART_LABELS: Record<ChartType, string> = {
  line: "Líneas",
  bar: "Barras",
  candle: "Velas",
  volume: "Volumen",
  ticks: "Ticks",
  range: "Barras de Rango",
  pnf: "Puntos y Figuras",
  renko: "Renko",
  kagi: "Kagi",
  tlb: "Rotura 3 Líneas",
};

// Custom candlestick shape
function CandlestickShape(props: any) {
  const { x, width, low, high, open, close, yScale } = props;
  if (!yScale) return null;
  const isUp = close >= open;
  const color = isUp ? "var(--color-success)" : "var(--color-danger)";
  const yHigh = yScale(high);
  const yLow = yScale(low);
  const yOpen = yScale(open);
  const yClose = yScale(close);
  const bodyTop = Math.min(yOpen, yClose);
  const bodyHeight = Math.max(Math.abs(yClose - yOpen), 1);
  const wickX = x + width / 2;
  const bodyW = Math.max(width * 0.6, 2);

  return (
    <g>
      <line x1={wickX} x2={wickX} y1={yHigh} y2={yLow} stroke={color} strokeWidth={1} />
      <rect
        x={x + (width - bodyW) / 2}
        y={bodyTop}
        width={bodyW}
        height={bodyHeight}
        fill={color}
        rx={1}
      />
    </g>
  );
}

export function PositionChart({
  symbol,
  entry,
  stopLoss,
  takeProfit,
  side,
  height = 200,
}: PositionChartProps) {
  const [chartType, setChartType] = useState<ChartType>("candle");
  const [iv, setIv] = useState("1m");
  const [klines, setKlines] = useState<Kline[]>([]);
  const [loading, setLoading] = useState(false);

  const loadKlines = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<Kline[]>(`/api/klines/${symbol}?interval=${iv}&limit=200`);
      setKlines(data);
    } catch {
      setKlines([]);
    } finally {
      setLoading(false);
    }
  }, [symbol, iv]);

  useEffect(() => {
    loadKlines();
    const id = setInterval(loadKlines, 5000);
    return () => clearInterval(id);
  }, [loadKlines]);

  const isLong = (side || "").toLowerCase() === "long" || (side || "").toUpperCase() === "BUY";
  void isLong;

  // All prices for Y domain
  const allPrices = useMemo(() => {
    const prices: number[] = [entry, stopLoss, takeProfit].filter((v) => v > 0);
    klines.forEach((k) => {
      prices.push(k.high, k.low, k.close);
    });
    return prices;
  }, [klines, entry, stopLoss, takeProfit]);

  const [minP, maxP] = useMemo(() => {
    if (allPrices.length === 0) return [0, 1];
    const min = Math.min(...allPrices);
    const max = Math.max(...allPrices);
    const pad = (max - min) * 0.1 || max * 0.05;
    return [Math.max(0, min - pad), max + pad];
  }, [allPrices]);

  const yScale = (v: number) => {
    if (maxP === minP) return height / 2;
    return height - ((v - minP) / (maxP - minP)) * height;
  };

  // --- Data transforms for special chart types ---

  // Line chart data
  const lineData = useMemo(
    () => klines.map((k) => ({ time: k.time, v: k.close })),
    [klines]
  );

  // Bar chart data (close prices as bars)
  const barData = useMemo(
    () => klines.map((k) => ({ time: k.time, v: k.close, up: k.close >= k.open })),
    [klines]
  );

  // Volume chart data
  const volumeData = useMemo(
    () => klines.map((k) => ({ time: k.time, volume: k.volume, up: k.close >= k.open })),
    [klines]
  );

  // Ticks chart data (price changes per tick)
  const ticksData = useMemo(() => {
    const ticks: { i: number; change: number; price: number }[] = [];
    let prev = klines[0]?.close || 0;
    klines.forEach((k, i) => {
      ticks.push({ i, change: k.close - prev, price: k.close });
      prev = k.close;
    });
    return ticks;
  }, [klines]);

  // Range bar data (high-low range)
  const rangeData = useMemo(
    () => klines.map((k) => ({ time: k.time, high: k.high, low: k.low, range: k.high - k.low, up: k.close >= k.open })),
    [klines]
  );

  // Point & Figure data
  const pnfData = useMemo(() => {
    if (klines.length < 2) return [];
    const boxSize = (maxP - minP) * 0.02 || 0.01;
    let direction: "up" | "down" = "up";
    let currentLevel = Math.floor(klines[0].close / boxSize) * boxSize;
    const cols: { x: number; y: number; type: "X" | "O" }[] = [];
    let colIdx = 0;
    let lastLevel = currentLevel;

    for (const k of klines) {
      const change = k.close - lastLevel;
      if (direction === "up") {
        if (change >= boxSize) {
          const steps = Math.floor(change / boxSize);
          for (let s = 0; s < steps; s++) {
            currentLevel += boxSize;
            cols.push({ x: colIdx, y: currentLevel, type: "X" });
          }
          lastLevel = currentLevel;
        } else if (change <= -boxSize * 3) {
          direction = "down";
          colIdx++;
          const steps = Math.floor(Math.abs(change) / boxSize);
          for (let s = 0; s < steps; s++) {
            currentLevel -= boxSize;
            cols.push({ x: colIdx, y: currentLevel, type: "O" });
          }
          lastLevel = currentLevel;
        }
      } else {
        if (change <= -boxSize) {
          const steps = Math.floor(Math.abs(change) / boxSize);
          for (let s = 0; s < steps; s++) {
            currentLevel -= boxSize;
            cols.push({ x: colIdx, y: currentLevel, type: "O" });
          }
          lastLevel = currentLevel;
        } else if (change >= boxSize * 3) {
          direction = "up";
          colIdx++;
          const steps = Math.floor(change / boxSize);
          for (let s = 0; s < steps; s++) {
            currentLevel += boxSize;
            cols.push({ x: colIdx, y: currentLevel, type: "X" });
          }
          lastLevel = currentLevel;
        }
      }
    }
    return cols;
  }, [klines, minP, maxP]);

  // Renko data
  const renkoData = useMemo(() => {
    if (klines.length < 2) return [];
    const brickSize = (maxP - minP) * 0.015 || 0.01;
    const bricks: { i: number; price: number; up: boolean }[] = [];
    let lastPrice = klines[0].close;
    let idx = 0;

    for (const k of klines) {
      const change = k.close - lastPrice;
      if (Math.abs(change) >= brickSize) {
        const numBricks = Math.floor(Math.abs(change) / brickSize);
        for (let b = 0; b < numBricks; b++) {
          if (change > 0) {
            lastPrice += brickSize;
            bricks.push({ i: idx++, price: lastPrice, up: true });
          } else {
            lastPrice -= brickSize;
            bricks.push({ i: idx++, price: lastPrice, up: false });
          }
        }
      }
    }
    return bricks;
  }, [klines, minP, maxP]);

  // Kagi data
  const kagiData = useMemo(() => {
    if (klines.length < 2) return [];
    const reversalAmount = (maxP - minP) * 0.03 || 0.01;
    const segments: { i: number; price: number; direction: "up" | "down" }[] = [];
    let direction: "up" | "down" = "up";
    let lastPrice = klines[0].close;
    segments.push({ i: 0, price: lastPrice, direction: "up" });
    let idx = 1;

    for (const k of klines) {
      const change = k.close - lastPrice;
      if (direction === "up" && change >= reversalAmount) {
        lastPrice = k.close;
        segments.push({ i: idx++, price: lastPrice, direction: "up" });
      } else if (direction === "down" && change <= -reversalAmount) {
        lastPrice = k.close;
        segments.push({ i: idx++, price: lastPrice, direction: "down" });
      } else if (direction === "up" && change <= -reversalAmount) {
        direction = "down";
        lastPrice = k.close;
        segments.push({ i: idx++, price: lastPrice, direction: "down" });
      } else if (direction === "down" && change >= reversalAmount) {
        direction = "up";
        lastPrice = k.close;
        segments.push({ i: idx++, price: lastPrice, direction: "up" });
      }
    }
    return segments;
  }, [klines, minP, maxP]);

  // Three Line Break data
  const tlbData = useMemo(() => {
    if (klines.length < 3) return [];
    const blocks: { i: number; high: number; low: number; up: boolean }[] = [];
    let idx = 0;
    for (const k of klines) {
      if (blocks.length === 0) {
        blocks.push({ i: idx++, high: k.close, low: k.open, up: k.close >= k.open });
      } else {
        const last3 = blocks.slice(-3);
        const lastBlock = blocks[blocks.length - 1];
        if (k.close > lastBlock.high) {
          blocks.push({ i: idx++, high: k.close, low: lastBlock.high, up: true });
        } else if (k.close < lastBlock.low) {
          blocks.push({ i: idx++, high: lastBlock.low, low: k.close, up: false });
        } else if (last3.length === 3 && last3.every((b) => b.up) && k.close < last3[0].low) {
          blocks.push({ i: idx++, high: last3[0].high, low: k.close, up: false });
        } else if (last3.length === 3 && last3.every((b) => !b.up) && k.close > last3[0].high) {
          blocks.push({ i: idx++, high: k.close, low: last3[0].low, up: true });
        }
      }
    }
    return blocks;
  }, [klines]);

  const tooltipStyle = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: 8,
    fontSize: 11,
  };

  const renderChart = () => {
    if (loading && klines.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-xs text-[var(--color-text-muted)]">
          Cargando datos...
        </div>
      );
    }

    if (klines.length === 0) {
      return (
        <div className="flex items-center justify-center h-full text-xs text-[var(--color-text-muted)]">
          Sin datos disponibles
        </div>
      );
    }

    switch (chartType) {
      // 1. Line Chart
      case "line":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={lineData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <defs>
                <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="time" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [`$${fmt(v)}`, "Close"]} labelFormatter={() => ""} />
              <Area type="monotone" dataKey="v" stroke="var(--color-primary)" strokeWidth={2} fill="url(#lineGrad)" dot={false} />
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </AreaChart>
          </ResponsiveContainer>
        );

      // 2. Bar Chart
      case "bar":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={barData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="time" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [`$${fmt(v)}`, "Close"]} labelFormatter={() => ""} />
              <Bar dataKey="v" radius={[2, 2, 0, 0]}>
                {barData.map((d, i) => (
                  <Cell key={i} fill={d.up ? "var(--color-success)" : "var(--color-danger)"} fillOpacity={0.7} />
                ))}
              </Bar>
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 3. Candlestick Chart
      case "candle":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={klines} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="time" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any, name: any) => [`$${fmt(v)}`, name]} labelFormatter={() => ""} />
              <Bar dataKey="high" shape={<CandlestickShape yScale={yScale} />} />
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 4. Volume Chart
      case "volume":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={volumeData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis hide />
              <XAxis dataKey="time" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [fmt(v), "Vol"]} labelFormatter={() => ""} />
              <Bar dataKey="volume" radius={[2, 2, 0, 0]}>
                {volumeData.map((d, i) => (
                  <Cell key={i} fill={d.up ? "var(--color-success)" : "var(--color-danger)"} fillOpacity={0.6} />
                ))}
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 5. Ticks Chart
      case "ticks":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={ticksData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis hide />
              <XAxis dataKey="i" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: any) => n === "price" ? [`$${fmt(v)}`, "Precio"] : [fmt(v), "Cambio"]} labelFormatter={() => ""} />
              <Bar dataKey="change" radius={[2, 2, 0, 0]}>
                {ticksData.map((d, i) => (
                  <Cell key={i} fill={d.change >= 0 ? "var(--color-success)" : "var(--color-danger)"} fillOpacity={0.7} />
                ))}
              </Bar>
              <ReferenceLine y={0} stroke="var(--color-border)" />
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 6. Range Bar Chart
      case "range":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rangeData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="time" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: any) => n === "high" ? [`$${fmt(v)}`, "High"] : n === "low" ? [`$${fmt(v)}`, "Low"] : [`$${fmt(v)}`, "Range"]} labelFormatter={() => ""} />
              <Bar dataKey="high" fill="transparent" />
              <Bar dataKey="low" radius={[2, 2, 0, 0]}>
                {rangeData.map((d, i) => (
                  <Cell key={i} fill={d.up ? "var(--color-success)" : "var(--color-danger)"} fillOpacity={0.6} />
                ))}
              </Bar>
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 7. Point & Figure Chart
      case "pnf":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <XAxis type="number" dataKey="x" name="Col" hide />
              <YAxis type="number" dataKey="y" name="Precio" domain={[minP, maxP]} hide />
              <ZAxis range={[60, 60]} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: any) => n === "y" ? [`$${fmt(v)}`, "Precio"] : [v, "Col"]} labelFormatter={() => ""} />
              <Scatter data={pnfData} fill="var(--color-primary)">
                {pnfData.map((d, i) => (
                  <Cell key={i} fill={d.type === "X" ? "var(--color-success)" : "var(--color-danger)"} />
                ))}
              </Scatter>
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ScatterChart>
          </ResponsiveContainer>
        );

      // 8. Renko Chart
      case "renko":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={renkoData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="i" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [`$${fmt(v)}`, "Precio"]} labelFormatter={() => ""} />
              <Bar dataKey="price" radius={[2, 2, 0, 0]}>
                {renkoData.map((d, i) => (
                  <Cell key={i} fill={d.up ? "var(--color-success)" : "var(--color-danger)"} fillOpacity={0.7} />
                ))}
              </Bar>
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 9. Kagi Chart
      case "kagi":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={kagiData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="i" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [`$${fmt(v)}`, "Precio"]} labelFormatter={() => ""} />
              <Line type="stepAfter" dataKey="price" stroke="var(--color-primary)" strokeWidth={2} dot={false} />
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        );

      // 10. Three Line Break
      case "tlb":
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={tlbData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
              <YAxis domain={[minP, maxP]} hide />
              <XAxis dataKey="i" hide />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: any) => [`$${fmt(v)}`, n === "high" ? "High" : "Low"]} labelFormatter={() => ""} />
              <Bar dataKey="high" fill="transparent" />
              <Bar dataKey="low" radius={[2, 2, 0, 0]}>
                {tlbData.map((d, i) => (
                  <Cell key={i} fill={d.up ? "var(--color-success)" : "var(--color-danger)"} fillOpacity={0.7} />
                ))}
              </Bar>
              <ReferenceLine y={entry} stroke="var(--color-text-muted)" strokeDasharray="4 4" label={{ value: "Entry", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 9 }} />
              {stopLoss > 0 && <ReferenceLine y={stopLoss} stroke="var(--color-danger)" strokeDasharray="3 3" label={{ value: "SL", position: "insideTopRight", fill: "var(--color-danger)", fontSize: 9 }} />}
              {takeProfit > 0 && <ReferenceLine y={takeProfit} stroke="var(--color-success)" strokeDasharray="3 3" label={{ value: "TP", position: "insideTopRight", fill: "var(--color-success)", fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        );

      default:
        return null;
    }
  };

  return (
    <div>
      {/* Chart type selector */}
      <div className="flex flex-wrap gap-1 mb-2">
        {(Object.keys(CHART_LABELS) as ChartType[]).map((t) => (
          <button
            key={t}
            onClick={() => setChartType(t)}
            className={`px-2 py-1 rounded-md text-[10px] font-medium transition-all ${
              chartType === t
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-3)]"
            }`}
          >
            {CHART_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Interval selector */}
      <div className="flex gap-1 mb-2">
        {["1m", "5m", "15m", "1h", "4h", "1d"].map((v) => (
          <button
            key={v}
            onClick={() => setIv(v)}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
              iv === v
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-3)]"
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div style={{ height }}>{renderChart()}</div>
    </div>
  );
}
