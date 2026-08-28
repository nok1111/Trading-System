// ─── Academy interactive widgets ──────────────────────────────────────────────
// Each widget simulates real Alvora UI so users learn by doing, not by reading
// code blocks. Widgets are self-contained, stateful, and visually match the
// actual app components they represent.

import { useState } from "react";
import {
  TrendingUp,
  CandlestickChart,
  Shield,
  Wallet,
  Bot,
  Calculator,
  AlertTriangle,
  Zap,
  Target,
  Activity,
  Layers,
  Grid3x3,
  Percent,
} from "lucide-react";
import type { WidgetType } from "../../data/tutorials";

// ─── Shared mini-components ────────────────────────────────────────────────────

function WidgetShell({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof TrendingUp;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl overflow-hidden border"
      style={{
        background: "var(--color-surface)",
        borderColor: "var(--color-border)",
      }}
    >
      <div
        className="flex items-center gap-2 px-3 py-2 border-b"
        style={{
          background: "var(--color-surface-2)",
          borderColor: "var(--color-border)",
        }}
      >
        <Icon size={14} className="text-[var(--color-primary)]" />
        <span className="text-[11px] font-bold text-[var(--color-text)] uppercase tracking-wide">
          {title}
        </span>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function MiniButton({
  active,
  onClick,
  children,
  color,
}: {
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all"
      style={{
        background: active ? color || "var(--color-primary)" : "var(--color-surface-2)",
        color: active ? "white" : "var(--color-text-muted)",
        border: active
          ? `1px solid ${color || "var(--color-primary)"}`
          : "1px solid var(--color-border)",
      }}
    >
      {children}
    </button>
  );
}

// ─── 1. Order Form Widget ─────────────────────────────────────────────────────

function OrderFormWidget() {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"market" | "limit" | "stop">("market");
  const [amount, setAmount] = useState("100");
  const [limitPrice, setLimitPrice] = useState("50000");
  const [stopPrice, setStopPrice] = useState("48000");

  const price = orderType === "limit" ? parseFloat(limitPrice) : 50000;
  const qty = parseFloat(amount) / price || 0;
  const fee = qty * price * 0.001;

  return (
    <WidgetShell title="Orden de Trading" icon={TrendingUp}>
      <div className="space-y-3">
        {/* Buy/Sell toggle */}
        <div className="grid grid-cols-2 gap-1.5">
          <MiniButton
            active={side === "buy"}
            onClick={() => setSide("buy")}
            color="var(--color-success)"
          >
            Comprar
          </MiniButton>
          <MiniButton
            active={side === "sell"}
            onClick={() => setSide("sell")}
            color="var(--color-danger)"
          >
            Vender
          </MiniButton>
        </div>

        {/* Order type */}
        <div className="flex gap-1.5">
          {(["market", "limit", "stop"] as const).map((t) => (
            <MiniButton
              key={t}
              active={orderType === t}
              onClick={() => setOrderType(t)}
            >
              {t === "market" ? "Market" : t === "limit" ? "Limit" : "Stop"}
            </MiniButton>
          ))}
        </div>

        {/* Inputs */}
        <div className="space-y-2">
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">
              {side === "buy" ? "Cantidad (USDT)" : "Cantidad (BTC)"}
            </label>
            <input
              type="text"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full mt-0.5 px-3 py-2 rounded-lg text-[13px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          {orderType === "limit" && (
            <div>
              <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">
                Precio Limit (USDT)
              </label>
              <input
                type="text"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                className="w-full mt-0.5 px-3 py-2 rounded-lg text-[13px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          )}
          {orderType === "stop" && (
            <div>
              <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">
                Precio Stop (USDT)
              </label>
              <input
                type="text"
                value={stopPrice}
                onChange={(e) => setStopPrice(e.target.value)}
                className="w-full mt-0.5 px-3 py-2 rounded-lg text-[13px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              />
            </div>
          )}
        </div>

        {/* Summary */}
        <div
          className="p-3 rounded-lg space-y-1.5 text-[11px]"
          style={{ background: "var(--color-surface-2)" }}
        >
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Precio</span>
            <span className="text-[var(--color-text)] font-bold">
              ${price.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Cantidad</span>
            <span className="text-[var(--color-text)] font-bold">
              {qty.toFixed(6)} BTC
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Fee (0.1%)</span>
            <span className="text-[var(--color-text)] font-bold">
              ${fee.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">Total</span>
            <span
              className="font-extrabold"
              style={{
                color:
                  side === "buy"
                    ? "var(--color-success)"
                    : "var(--color-danger)",
              }}
            >
              ${(qty * price + fee).toFixed(2)}
            </span>
          </div>
        </div>

        <button
          className="w-full py-2.5 rounded-lg text-[13px] font-bold text-white transition-colors"
          style={{
            background:
              side === "buy" ? "var(--color-success)" : "var(--color-danger)",
          }}
        >
          {side === "buy" ? "Comprar BTC" : "Vender BTC"}
        </button>
      </div>
    </WidgetShell>
  );
}

// ─── 2. Candlestick Patterns Widget ───────────────────────────────────────────

function CandlestickPatternsWidget() {
  const [pattern, setPattern] = useState("doji");

  const patterns: Record<string, { name: string; candles: number[][]; desc: string }> = {
    doji: {
      name: "Doji",
      candles: [[50, 55, 45, 50.5]],
      desc: "Apertura ≈ Cierre. Indica indecisión.",
    },
    hammer: {
      name: "Hammer",
      candles: [[55, 56, 40, 54]],
      desc: "Cuerpo pequeño arriba, mecha inferior larga. Reversión alcista.",
    },
    "bullish-engulfing": {
      name: "Bullish Engulfing",
      candles: [
        [55, 56, 48, 49],
        [49, 57, 47, 56],
      ],
      desc: "Vela verde grande engulle a la roja anterior. Reversión alcista.",
    },
    "morning-star": {
      name: "Morning Star",
      candles: [
        [55, 56, 44, 45],
        [45, 47, 42, 44],
        [44, 55, 43, 54],
      ],
      desc: "3 velas: roja grande, pequeña, verde grande. Reversión alcista.",
    },
  };

  const current = patterns[pattern];
  const allHigh = Math.max(...current.candles.map((c) => c[1]));
  const allLow = Math.min(...current.candles.map((c) => c[2]));
  const range = allHigh - allLow || 1;

  return (
    <WidgetShell title="Patrones de Velas" icon={CandlestickChart}>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(patterns).map(([key, p]) => (
            <MiniButton
              key={key}
              active={pattern === key}
              onClick={() => setPattern(key)}
            >
              {p.name}
            </MiniButton>
          ))}
        </div>

        {/* Candlestick chart */}
        <div className="flex items-end justify-center gap-3 h-32 px-4 py-2 rounded-lg" style={{ background: "var(--color-surface-2)" }}>
          {current.candles.map((c, i) => {
            const [open, high, low, close] = c;
            const isBull = close >= open;
            const bodyTop = ((allHigh - Math.max(open, close)) / range) * 100;
            const bodyBot = ((allHigh - Math.min(open, close)) / range) * 100;
            const wickTop = ((allHigh - high) / range) * 100;
            const wickBot = ((allHigh - low) / range) * 100;
            const color = isBull ? "var(--color-success)" : "var(--color-danger)";
            return (
              <div key={i} className="relative flex flex-col items-center" style={{ height: "100%" }}>
                {/* Upper wick */}
                <div style={{ height: `${bodyTop - wickTop}%`, width: "2px", background: color, marginLeft: "auto", marginRight: "auto" }} />
                {/* Body */}
                <div
                  style={{
                    height: `${bodyBot - bodyTop}%`,
                    width: "24px",
                    background: color,
                    borderRadius: "2px",
                  }}
                />
                {/* Lower wick */}
                <div style={{ height: `${wickBot - bodyBot}%`, width: "2px", background: color, marginLeft: "auto", marginRight: "auto" }} />
              </div>
            );
          })}
        </div>

        <div className="p-3 rounded-lg text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="font-bold text-[var(--color-text)] mb-1">{current.name}</div>
          <div className="text-[var(--color-text-muted)]">{current.desc}</div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 3. Support/Resistance Widget ─────────────────────────────────────────────

function SupportResistanceWidget() {
  const [level, setLevel] = useState<"support" | "resistance" | "breakout">("support");

  const configs = {
    support: { color: "var(--color-success)", label: "Soporte", desc: "El precio rebota al alza. Presión compradora." },
    resistance: { color: "var(--color-danger)", label: "Resistencia", desc: "El precio rebota a la baja. Presión vendedora." },
    breakout: { color: "var(--color-warning)", label: "Breakout", desc: "El precio rompe el nivel con volumen. Nueva tendencia." },
  };

  const cfg = configs[level];
  const points = level === "breakout"
    ? [50, 52, 48, 51, 49, 53, 58, 62, 65]
    : level === "support"
    ? [55, 50, 52, 50, 53, 50, 54, 51, 55]
    : [45, 50, 48, 52, 49, 51, 48, 50, 47];

  const lineY = level === "breakout" ? 55 : level === "support" ? 50 : 52;
  const maxVal = 70;

  return (
    <WidgetShell title="Soporte y Resistencia" icon={Activity}>
      <div className="space-y-3">
        <div className="flex gap-1.5">
          {(["support", "resistance", "breakout"] as const).map((l) => (
            <MiniButton key={l} active={level === l} onClick={() => setLevel(l)}>
              {configs[l].label}
            </MiniButton>
          ))}
        </div>

        {/* Mini chart */}
        <div className="relative h-32 rounded-lg p-2" style={{ background: "var(--color-surface-2)" }}>
          {/* S/R line */}
          <div
            className="absolute left-2 right-2 border-dashed"
            style={{
              top: `${100 - (lineY / maxVal) * 100}%`,
              borderTop: `2px dashed ${cfg.color}`,
              opacity: 0.7,
            }}
          >
            <span
              className="absolute -top-4 right-0 text-[9px] font-bold px-1.5 rounded"
              style={{ background: cfg.color, color: "white" }}
            >
              {cfg.label}
            </span>
          </div>
          {/* Price line */}
          <svg className="absolute inset-2" width="calc(100% - 16px)" height="calc(100% - 16px)" preserveAspectRatio="none">
            <polyline
              points={points
                .map((p, i) => `${(i / (points.length - 1)) * 100},${100 - (p / maxVal) * 100}`)
                .join(" ")}
              fill="none"
              stroke={cfg.color}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        </div>

        <div className="p-3 rounded-lg text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="font-bold mb-1" style={{ color: cfg.color }}>{cfg.label}</div>
          <div className="text-[var(--color-text-muted)]">{cfg.desc}</div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 4. Moving Averages Widget ────────────────────────────────────────────────

function MovingAveragesWidget() {
  const [maType, setMaType] = useState<"sma" | "ema" | "crossover">("crossover");

  const configs = {
    sma: { label: "SMA(20)", color: "#3b82f6", desc: "Promedio simple de las últimas 20 velas. Suaviza el ruido." },
    ema: { label: "EMA(20)", color: "#f59e0b", desc: "Da más peso a precios recientes. Reacciona más rápido." },
    crossover: { label: "Cruce EMA", color: "var(--color-success)", desc: "Golden Cross: EMA50 cruza por encima de EMA200. Señal alcista." },
  };

  const cfg = configs[maType];

  // Simulated price + MA data
  const price = [45, 47, 44, 48, 50, 49, 52, 55, 53, 57, 60, 58, 62, 65, 63];
  const sma20 = price.map((_, i) => {
    if (i < 4) return price[i];
    return price.slice(Math.max(0, i - 4), i + 1).reduce((a, b) => a + b, 0) / 5;
  });
  const emaFast = price.map((p, i) => i === 0 ? p : (p * 0.3 + sma20[i - 1] * 0.7));
  const emaSlow = price.map((p, i) => i === 0 ? p : (p * 0.1 + sma20[i - 1] * 0.9));

  const lines = maType === "sma" ? [{ data: sma20, color: cfg.color, label: "SMA" }]
    : maType === "ema" ? [{ data: emaFast, color: cfg.color, label: "EMA" }]
    : [
        { data: emaFast, color: "#3b82f6", label: "EMA50" },
        { data: emaSlow, color: "#f59e0b", label: "EMA200" },
      ];

  const maxVal = Math.max(...price);

  return (
    <WidgetShell title="Medias Móviles" icon={TrendingUp}>
      <div className="space-y-3">
        <div className="flex gap-1.5">
          {(["sma", "ema", "crossover"] as const).map((t) => (
            <MiniButton key={t} active={maType === t} onClick={() => setMaType(t)}>
              {configs[t].label}
            </MiniButton>
          ))}
        </div>

        {/* Chart */}
        <div className="relative h-32 rounded-lg p-2" style={{ background: "var(--color-surface-2)" }}>
          <svg className="absolute inset-2" width="calc(100% - 16px)" height="calc(100% - 16px)" preserveAspectRatio="none">
            {/* Price line */}
            <polyline
              points={price.map((p, i) => `${(i / (price.length - 1)) * 100},${100 - (p / maxVal) * 90}`).join(" ")}
              fill="none"
              stroke="var(--color-text)"
              strokeWidth="1.5"
              opacity="0.5"
              vectorEffect="non-scaling-stroke"
            />
            {/* MA lines */}
            {lines.map((line, idx) => (
              <polyline
                key={idx}
                points={line.data.map((p, i) => `${(i / (line.data.length - 1)) * 100},${100 - (p / maxVal) * 90}`).join(" ")}
                fill="none"
                stroke={line.color}
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <div className="w-3 h-0.5" style={{ background: "var(--color-text)" }} />
            <span className="text-[var(--color-text-muted)]">Precio</span>
          </span>
          {lines.map((line, i) => (
            <span key={i} className="flex items-center gap-1">
              <div className="w-3 h-0.5" style={{ background: line.color }} />
              <span className="text-[var(--color-text-muted)]">{line.label}</span>
            </span>
          ))}
        </div>

        <div className="p-3 rounded-lg text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="text-[var(--color-text-muted)]">{cfg.desc}</div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 5. RSI/MACD Widget ───────────────────────────────────────────────────────

function RsiMacdWidget() {
  const [indicator, setIndicator] = useState<"rsi" | "macd">("rsi");

  const rsiData = [35, 28, 25, 30, 38, 45, 52, 60, 68, 72, 75, 78];
  const macdData = [-5, -8, -10, -7, -3, 0, 3, 6, 8, 5, 2, -1];
  const signalData = [-3, -5, -7, -8, -6, -4, -2, 0, 2, 4, 5, 4];

  const data = indicator === "rsi" ? rsiData : macdData;
  const maxVal = indicator === "rsi" ? 100 : Math.max(...macdData.map(Math.abs)) * 1.2;

  return (
    <WidgetShell title={indicator === "rsi" ? "RSI (14)" : "MACD"} icon={Activity}>
      <div className="space-y-3">
        <div className="flex gap-1.5">
          <MiniButton active={indicator === "rsi"} onClick={() => setIndicator("rsi")}>RSI</MiniButton>
          <MiniButton active={indicator === "macd"} onClick={() => setIndicator("macd")}>MACD</MiniButton>
        </div>

        {/* Indicator chart */}
        <div className="relative h-28 rounded-lg p-2" style={{ background: "var(--color-surface-2)" }}>
          {indicator === "rsi" && (
            <>
              {/* Overbought/oversold zones */}
              <div className="absolute left-2 right-2" style={{ top: "20%", height: "10%", background: "color-mix(in srgb, var(--color-danger) 10%, transparent)", borderRadius: "4px" }} />
              <div className="absolute left-2 right-2" style={{ top: "70%", height: "10%", background: "color-mix(in srgb, var(--color-success) 10%, transparent)", borderRadius: "4px" }} />
              {/* Lines at 70 and 30 */}
              <div className="absolute left-2 right-2 border-t border-dashed" style={{ top: "30%", borderColor: "var(--color-danger)", opacity: 0.4 }} />
              <div className="absolute left-2 right-2 border-t border-dashed" style={{ top: "70%", borderColor: "var(--color-success)", opacity: 0.4 }} />
            </>
          )}
          <svg className="absolute inset-2" width="calc(100% - 16px)" height="calc(100% - 16px)" preserveAspectRatio="none">
            <polyline
              points={data.map((v, i) => `${(i / (data.length - 1)) * 100},${indicator === "rsi" ? 100 - v : 50 - (v / maxVal) * 40}`).join(" ")}
              fill="none"
              stroke={indicator === "rsi" ? "var(--color-primary)" : "#3b82f6"}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
            {indicator === "macd" && (
              <polyline
                points={signalData.map((v, i) => `${(i / (signalData.length - 1)) * 100},${50 - (v / maxVal) * 40}`).join(" ")}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="1.5"
                strokeDasharray="3,2"
                vectorEffect="non-scaling-stroke"
              />
            )}
            {indicator === "macd" && (
              <line x1="0" y1="50" x2="100" y2="50" stroke="var(--color-border)" strokeWidth="1" />
            )}
          </svg>
        </div>

        {/* Labels */}
        {indicator === "rsi" ? (
          <div className="flex justify-between text-[10px] font-bold">
            <span className="text-[var(--color-success)]">Oversold (30)</span>
            <span className="text-[var(--color-text-muted)]">RSI: {rsiData[rsiData.length - 1]}</span>
            <span className="text-[var(--color-danger)]">Overbought (70)</span>
          </div>
        ) : (
          <div className="flex justify-between text-[10px] font-bold">
            <span className="flex items-center gap-1">
              <div className="w-3 h-0.5" style={{ background: "#3b82f6" }} />
              <span className="text-[var(--color-text-muted)]">MACD</span>
            </span>
            <span className="flex items-center gap-1">
              <div className="w-3 h-0.5 border-dashed" style={{ borderTop: "1.5px dashed #f59e0b" }} />
              <span className="text-[var(--color-text-muted)]">Signal</span>
            </span>
          </div>
        )}

        <div className="p-3 rounded-lg text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="text-[var(--color-text-muted)]">
            {indicator === "rsi"
              ? "RSI > 70 = sobrecomprado. RSI < 30 = sobrevendido."
              : "MACD cruza por encima de Signal = alcista. Por debajo = bajista."}
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 6. Volume Profile Widget ─────────────────────────────────────────────────

function VolumeProfileWidget() {
  const levels = [
    { price: 52000, vol: 15 },
    { price: 51000, vol: 45 },
    { price: 50000, vol: 100, poc: true },
    { price: 49000, vol: 60 },
    { price: 48000, vol: 20 },
  ];
  const maxVol = Math.max(...levels.map((l) => l.vol));

  return (
    <WidgetShell title="Volume Profile" icon={Layers}>
      <div className="space-y-2">
        {levels.map((l) => (
          <div key={l.price} className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-[var(--color-text-muted)] w-14 text-right">
              ${l.price.toLocaleString()}
            </span>
            <div className="flex-1 h-5 rounded bg-[var(--color-surface-2)] overflow-hidden relative">
              <div
                className="h-full rounded transition-all"
                style={{
                  width: `${(l.vol / maxVol) * 100}%`,
                  background: l.poc ? "var(--color-warning)" : "var(--color-primary)",
                  opacity: l.poc ? 1 : 0.6,
                }}
              />
              {l.poc && (
                <span className="absolute right-1 top-1/2 -translate-y-1/2 text-[8px] font-bold text-white">
                  POC
                </span>
              )}
            </div>
          </div>
        ))}
        <div className="p-2.5 rounded-lg text-[11px] mt-2" style={{ background: "var(--color-surface-2)" }}>
          <span className="font-bold text-[var(--color-warning)]">POC</span>
          <span className="text-[var(--color-text-muted)]"> = Point of Control. Nivel con más volumen. El precio tiende a volver aquí.</span>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 7. Grid Bot Visualization ────────────────────────────────────────────────

function GridBotVizWidget() {
  const [gridLevels, setGridLevels] = useState(8);
  const [range] = useState({ low: 40000, high: 60000 });
  const stepSize = (range.high - range.low) / gridLevels;
  const currentPrice = 50000;

  return (
    <WidgetShell title="Grid Bot" icon={Bot}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Niveles</label>
            <input
              type="range"
              min="4"
              max="15"
              value={gridLevels}
              onChange={(e) => setGridLevels(parseInt(e.target.value))}
              className="w-full mt-1"
            />
            <span className="text-[11px] font-bold text-[var(--color-text)]">{gridLevels} niveles</span>
          </div>
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Rango</label>
            <div className="text-[11px] font-bold text-[var(--color-text)] mt-1">
              ${range.low.toLocaleString()} - ${range.high.toLocaleString()}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)]">
              Step: ${stepSize.toFixed(0)}
            </div>
          </div>
        </div>

        {/* Grid visualization */}
        <div className="relative h-40 rounded-lg p-3" style={{ background: "var(--color-surface-2)" }}>
          {Array.from({ length: gridLevels }, (_, i) => {
            const price = range.low + (stepSize * i);
            const yPct = 100 - ((price - range.low) / (range.high - range.low)) * 100;
            const isBuy = price < currentPrice;
            return (
              <div
                key={i}
                className="absolute left-3 right-3 flex items-center gap-2"
                style={{ top: `${yPct}%` }}
              >
                <div
                  className="flex-1 border-t border-dashed"
                  style={{ borderColor: isBuy ? "var(--color-success)" : "var(--color-danger)", opacity: 0.5 }}
                />
                <span
                  className="text-[8px] font-bold px-1.5 rounded"
                  style={{
                    background: isBuy ? "var(--color-success)" : "var(--color-danger)",
                    color: "white",
                  }}
                >
                  {isBuy ? "BUY" : "SELL"} ${price.toFixed(0)}
                </span>
              </div>
            );
          })}
          {/* Current price line */}
          <div
            className="absolute left-3 right-3 border-t-2"
            style={{ top: `${100 - ((currentPrice - range.low) / (range.high - range.low)) * 100}%`, borderColor: "var(--color-primary)" }}
          >
            <span className="absolute -top-4 right-0 text-[9px] font-bold px-1.5 rounded" style={{ background: "var(--color-primary)", color: "white" }}>
              Precio: ${currentPrice.toLocaleString()}
            </span>
          </div>
        </div>

        <div className="p-3 rounded-lg text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="text-[var(--color-text-muted)]">
            El bot compra en niveles verdes y vende en rojos. Funciona mejor en mercados laterales.
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 8. DCA Averaging Widget ──────────────────────────────────────────────────

function DcaAveragingWidget() {
  const purchases = [
    { week: 1, price: 50000, amount: 100 },
    { week: 2, price: 45000, amount: 100 },
    { week: 3, price: 42000, amount: 100 },
    { week: 4, price: 48000, amount: 100 },
    { week: 5, price: 52000, amount: 100 },
  ];
  const totalSpent = purchases.reduce((s, p) => s + p.amount, 0);
  const totalBtc = purchases.reduce((s, p) => s + p.amount / p.price, 0);
  const avgPrice = totalSpent / totalBtc;
  const currentValue = totalBtc * purchases[purchases.length - 1].price;
  const pnl = ((currentValue / totalSpent) - 1) * 100;

  return (
    <WidgetShell title="DCA Bot — Dollar Cost Averaging" icon={Calculator}>
      <div className="space-y-3">
        <div className="space-y-1.5">
          {purchases.map((p) => (
            <div key={p.week} className="flex items-center gap-2 p-2 rounded-lg" style={{ background: "var(--color-surface-2)" }}>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] w-14">Sem {p.week}</span>
              <span className="text-[11px] text-[var(--color-text)]">${p.amount}</span>
              <span className="text-[10px] text-[var(--color-text-muted)]">@</span>
              <span className="text-[11px] font-bold text-[var(--color-text)]">${p.price.toLocaleString()}</span>
              <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
                {(p.amount / p.price).toFixed(6)} BTC
              </span>
            </div>
          ))}
        </div>

        <div className="p-3 rounded-lg space-y-1.5 text-[11px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Total invertido</span>
            <span className="text-[var(--color-text)] font-bold">${totalSpent}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">BTC acumulado</span>
            <span className="text-[var(--color-text)] font-bold">{totalBtc.toFixed(6)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Precio promedio</span>
            <span className="text-[var(--color-text)] font-bold">${avgPrice.toFixed(0)}</span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">P&L actual</span>
            <span className="font-extrabold" style={{ color: pnl >= 0 ? "var(--color-success)" : "var(--color-danger)" }}>
              {pnl >= 0 ? "+" : ""}{pnl.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 9. Position Sizing Widget ────────────────────────────────────────────────

function PositionSizingWidget() {
  const [account, setAccount] = useState("10000");
  const [riskPct, setRiskPct] = useState("1");
  const [entry, setEntry] = useState("50000");
  const [stop, setStop] = useState("48000");

  const riskAmount = (parseFloat(account) * parseFloat(riskPct)) / 100;
  const stopDistance = Math.abs(parseFloat(entry) - parseFloat(stop));
  const positionSize = stopDistance > 0 ? riskAmount / stopDistance : 0;
  const positionValue = positionSize * parseFloat(entry);

  return (
    <WidgetShell title="Position Sizing" icon={Target}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Capital (USDT)</label>
            <input type="text" value={account} onChange={(e) => setAccount(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Risk %</label>
            <input type="text" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Entry</label>
            <input type="text" value={entry} onChange={(e) => setEntry(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Stop-Loss</label>
            <input type="text" value={stop} onChange={(e) => setStop(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
        </div>

        <div className="p-3 rounded-lg space-y-1.5 text-[12px]" style={{ background: "color-mix(in srgb, var(--color-primary) 8%, var(--color-surface))", border: "1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)" }}>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Risk por trade</span>
            <span className="text-[var(--color-danger)] font-bold">${riskAmount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Distancia al stop</span>
            <span className="text-[var(--color-text)] font-bold">${stopDistance.toFixed(0)}</span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">Tamaño posición</span>
            <span className="text-[var(--color-primary)] font-extrabold">{positionSize.toFixed(6)} BTC</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)] font-bold">Valor posición</span>
            <span className="text-[var(--color-primary)] font-extrabold">${positionValue.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 10. Correlation Matrix Widget ────────────────────────────────────────────

function CorrelationMatrixWidget() {
  const assets = ["BTC", "ETH", "SOL", "USDT"];
  const matrix: number[][] = [
    [1.0, 0.85, 0.75, 0.0],
    [0.85, 1.0, 0.80, 0.0],
    [0.75, 0.80, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
  ];

  const getColor = (v: number) => {
    if (v >= 0.8) return "var(--color-danger)";
    if (v >= 0.5) return "var(--color-warning)";
    if (v >= 0.3) return "#f59e0b";
    if (v > 0) return "var(--color-success)";
    return "var(--color-surface-2)";
  };

  return (
    <WidgetShell title="Matriz de Correlación" icon={Grid3x3} >
      <div className="space-y-2">
        <div className="grid grid-cols-5 gap-1 text-center text-[10px]">
          <div></div>
          {assets.map((a) => (
            <div key={a} className="font-bold text-[var(--color-text-muted)]">{a}</div>
          ))}
          {matrix.map((row, i) => (
            <>
              <div key={`label-${i}`} className="font-bold text-[var(--color-text-muted)] flex items-center justify-center">{assets[i]}</div>
              {row.map((v, j) => (
                <div
                  key={`${i}-${j}`}
                  className="rounded flex items-center justify-center font-bold text-[10px] h-7"
                  style={{
                    background: `color-mix(in srgb, ${getColor(v)} ${Math.abs(v) * 60}%, var(--color-surface-2))`,
                    color: Math.abs(v) > 0.5 ? "white" : "var(--color-text)",
                  }}
                >
                  {v.toFixed(2)}
                </div>
              ))}
            </>
          ))}
        </div>
        <div className="p-2.5 rounded-lg text-[11px]" style={{ background: "var(--color-surface-2)" }}>
          <span className="text-[var(--color-text-muted)]">BTC y ETH tienen correlación 0.85 — caen juntos. Diversifica con activos de baja correlación.</span>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 11. Leverage Calculator Widget ───────────────────────────────────────────

function LeverageCalculatorWidget() {
  const [capital, setCapital] = useState("1000");
  const [leverage, setLeverage] = useState("10");

  const cap = parseFloat(capital) || 0;
  const lev = parseInt(leverage) || 1;
  const positionSize = cap * lev;
  const liquidationDrop = 100 / lev; // % drop to liquidate

  return (
    <WidgetShell title="Calculadora de Apalancamiento" icon={Zap}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Capital</label>
            <input type="text" value={capital} onChange={(e) => setCapital(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Apalancamiento</label>
            <select value={leverage} onChange={(e) => setLeverage(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]">
              {["1", "2", "5", "10", "20", "50"].map((l) => <option key={l} value={l}>{l}x</option>)}
            </select>
          </div>
        </div>

        <div className="p-3 rounded-lg space-y-1.5 text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Tamaño posición</span>
            <span className="text-[var(--color-text)] font-bold">${positionSize.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Precio +5% → ganancia</span>
            <span className="text-[var(--color-success)] font-bold">+{(lev * 5).toFixed(0)}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Precio -5% → pérdida</span>
            <span className="text-[var(--color-danger)] font-bold">-{(lev * 5).toFixed(0)}%</span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold flex items-center gap-1">
              <AlertTriangle size={11} className="text-[var(--color-danger)]" />
              Liquidación
            </span>
            <span className="text-[var(--color-danger)] font-extrabold">-{liquidationDrop.toFixed(1)}%</span>
          </div>
        </div>

        {lev >= 10 && (
          <div className="p-2.5 rounded-lg text-[11px] flex items-center gap-2" style={{ background: "color-mix(in srgb, var(--color-danger) 10%, transparent)", border: "1px solid var(--color-danger)" }}>
            <AlertTriangle size={14} className="text-[var(--color-danger)] flex-shrink-0" />
            <span className="text-[var(--color-text)]">90% de traders novatos pierden con {lev}x. Reduce el apalancamiento.</span>
          </div>
        )}
      </div>
    </WidgetShell>
  );
}

// ─── 12. SL/TP Visualizer Widget ──────────────────────────────────────────────

function SlTpVisualizerWidget() {
  const [entry, setEntry] = useState("50000");
  const [sl, setSl] = useState("48000");
  const [tp, setTp] = useState("54000");

  const e = parseFloat(entry), s = parseFloat(sl), t = parseFloat(tp);
  const risk = Math.abs(e - s);
  const reward = Math.abs(t - e);
  const rr = risk > 0 ? reward / risk : 0;
  const min = Math.min(s, e, t) * 0.98;
  const max = Math.max(s, e, t) * 1.02;
  const range = max - min;

  const pos = (v: number) => 100 - ((v - min) / range) * 100;

  return (
    <WidgetShell title="Stop-Loss / Take-Profit" icon={Shield}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="text-[9px] text-[var(--color-text-muted)] font-bold uppercase">Entry</label>
            <input type="text" value={entry} onChange={(e) => setEntry(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[11px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
          <div>
            <label className="text-[9px] text-[var(--color-danger)] font-bold uppercase">Stop</label>
            <input type="text" value={sl} onChange={(e) => setSl(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[11px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-danger)]" />
          </div>
          <div>
            <label className="text-[9px] text-[var(--color-success)] font-bold uppercase">Target</label>
            <input type="text" value={tp} onChange={(e) => setTp(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[11px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-success)]" />
          </div>
        </div>

        {/* Visual chart */}
        <div className="relative h-32 rounded-lg p-2" style={{ background: "var(--color-surface-2)" }}>
          {/* TP zone */}
          <div className="absolute left-2 right-2" style={{ top: `${pos(t)}%`, height: `${pos(e) - pos(t)}%`, background: "color-mix(in srgb, var(--color-success) 10%, transparent)", borderRadius: "4px" }} />
          {/* SL zone */}
          <div className="absolute left-2 right-2" style={{ top: `${pos(e)}%`, height: `${pos(s) - pos(e)}%`, background: "color-mix(in srgb, var(--color-danger) 10%, transparent)", borderRadius: "4px" }} />
          {/* Entry line */}
          <div className="absolute left-2 right-2 border-t-2" style={{ top: `${pos(e)}%`, borderColor: "var(--color-primary)" }}>
            <span className="absolute -top-4 left-0 text-[9px] font-bold px-1.5 rounded" style={{ background: "var(--color-primary)", color: "white" }}>Entry ${e.toLocaleString()}</span>
          </div>
          {/* SL line */}
          <div className="absolute left-2 right-2 border-t border-dashed" style={{ top: `${pos(s)}%`, borderColor: "var(--color-danger)" }}>
            <span className="absolute -top-4 right-0 text-[9px] font-bold px-1.5 rounded" style={{ background: "var(--color-danger)", color: "white" }}>SL ${s.toLocaleString()}</span>
          </div>
          {/* TP line */}
          <div className="absolute left-2 right-2 border-t border-dashed" style={{ top: `${pos(t)}%`, borderColor: "var(--color-success)" }}>
            <span className="absolute -bottom-4 right-0 text-[9px] font-bold px-1.5 rounded" style={{ background: "var(--color-success)", color: "white" }}>TP ${t.toLocaleString()}</span>
          </div>
        </div>

        <div className="p-3 rounded-lg space-y-1 text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Risk</span>
            <span className="text-[var(--color-danger)] font-bold">${risk.toFixed(0)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Reward</span>
            <span className="text-[var(--color-success)] font-bold">${reward.toFixed(0)}</span>
          </div>
          <div className="flex justify-between pt-1 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">Ratio R:R</span>
            <span className="font-extrabold" style={{ color: rr >= 2 ? "var(--color-success)" : rr >= 1 ? "var(--color-warning)" : "var(--color-danger)" }}>
              1:{rr.toFixed(2)} {rr >= 2 ? "✓" : rr < 1 ? "✗" : "⚠"}
            </span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 13. Risk/Reward Calculator ───────────────────────────────────────────────

function RiskRewardWidget() {
  return <SlTpVisualizerWidget />;
}

// ─── 14. Tax Calculator Widget ────────────────────────────────────────────────

function TaxCalculatorWidget() {
  const [country, setCountry] = useState("ES");
  const [gain, setGain] = useState("5000");

  const rates: Record<string, { rate: number; name: string; allowance: number }> = {
    ES: { rate: 0.28, name: "España", allowance: 0 },
    US: { rate: 0.20, name: "USA (LT)", allowance: 0 },
    UK: { rate: 0.20, name: "UK", allowance: 3000 },
    DE: { rate: 0.26375, name: "Alemania", allowance: 0 },
  };

  const cfg = rates[country];
  const taxable = Math.max(0, parseFloat(gain) - cfg.allowance);
  const tax = taxable * cfg.rate;
  const net = parseFloat(gain) - tax;

  return (
    <WidgetShell title="Tax Studio" icon={Calculator}>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(rates).map(([code, r]) => (
            <MiniButton key={code} active={country === code} onClick={() => setCountry(code)}>
              {r.name}
            </MiniButton>
          ))}
        </div>

        <div>
          <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Ganancia (USDT)</label>
          <input type="text" value={gain} onChange={(e) => setGain(e.target.value)} className="w-full mt-0.5 px-3 py-2 rounded-lg text-[13px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
        </div>

        <div className="p-3 rounded-lg space-y-1.5 text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          {cfg.allowance > 0 && (
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Allowance</span>
              <span className="text-[var(--color-text)] font-bold">${cfg.allowance.toLocaleString()}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Base imponible</span>
            <span className="text-[var(--color-text)] font-bold">${taxable.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Tasa</span>
            <span className="text-[var(--color-text)] font-bold">{(cfg.rate * 100).toFixed(1)}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Impuesto</span>
            <span className="text-[var(--color-danger)] font-bold">-${tax.toFixed(2)}</span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">Ganancia neta</span>
            <span className="text-[var(--color-success)] font-extrabold">${net.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 15. Wallet Safety Widget ─────────────────────────────────────────────────

function WalletSafetyWidget() {
  const [selected, setSelected] = useState<"hot" | "cold">("cold");

  const configs = {
    hot: {
      icon: "📱",
      title: "Hot Wallet",
      examples: "MetaMask, Trust, Phantom",
      pros: ["Conveniente", "DeFi y dApps", "Acceso rápido"],
      cons: ["Conectada a internet", "Vulnerable a hacks", "Riesgo de phishing"],
      recommended: "5-10% de tus crypto",
      color: "var(--color-warning)",
    },
    cold: {
      icon: "🔒",
      title: "Cold Wallet",
      examples: "Ledger, Trezor, GridPlus",
      pros: ["Offline = seguro", "Claves nunca tocan internet", "Estándar de seguridad"],
      cons: ["Menos conveniente", "Costo (~$80-150)", "Requiere hardware físico"],
      recommended: "90%+ de tus crypto",
      color: "var(--color-success)",
    },
  };

  const cfg = configs[selected];

  return (
    <WidgetShell title="Wallet Safety" icon={Wallet}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          {(Object.keys(configs) as ("hot" | "cold")[]).map((k) => (
            <button
              key={k}
              onClick={() => setSelected(k)}
              className="p-3 rounded-xl text-center transition-all"
              style={{
                background: selected === k ? `color-mix(in srgb, ${configs[k].color} 12%, var(--color-surface))` : "var(--color-surface-2)",
                border: selected === k ? `2px solid ${configs[k].color}` : "1px solid var(--color-border)",
              }}
            >
              <div className="text-[24px]">{configs[k].icon}</div>
              <div className="text-[11px] font-bold mt-1" style={{ color: selected === k ? configs[k].color : "var(--color-text-muted)" }}>
                {configs[k].title}
              </div>
            </button>
          ))}
        </div>

        <div className="p-3 rounded-lg space-y-2 text-[11px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="text-[var(--color-text-muted)] font-bold">{cfg.examples}</div>
          <div>
            <div className="text-[var(--color-success)] font-bold mb-1">✓ Pros:</div>
            {cfg.pros.map((p) => <div key={p} className="text-[var(--color-text)]">• {p}</div>)}
          </div>
          <div>
            <div className="text-[var(--color-danger)] font-bold mb-1">✗ Contras:</div>
            {cfg.cons.map((c) => <div key={c} className="text-[var(--color-text)]">• {c}</div>)}
          </div>
          <div className="pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)]">Recomendado: </span>
            <span className="font-bold" style={{ color: cfg.color }}>{cfg.recommended}</span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 16. Staking Calculator Widget ────────────────────────────────────────────

function StakingCalculatorWidget() {
  const [amount, setAmount] = useState("10");
  const [apy, setApy] = useState("5");

  const amt = parseFloat(amount) || 0;
  const rate = parseFloat(apy) || 0;
  const yearly = amt * (rate / 100);
  const monthly = yearly / 12;
  const after5y = amt * Math.pow(1 + rate / 100, 5);

  return (
    <WidgetShell title="Staking Calculator" icon={Percent}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">ETH</label>
            <input type="text" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
          <div>
            <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">APY %</label>
            <input type="text" value={apy} onChange={(e) => setApy(e.target.value)} className="w-full mt-0.5 px-2 py-1.5 rounded-lg text-[12px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]" />
          </div>
        </div>

        <div className="p-3 rounded-lg space-y-1.5 text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Reward mensual</span>
            <span className="text-[var(--color-success)] font-bold">{monthly.toFixed(4)} ETH</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Reward anual</span>
            <span className="text-[var(--color-success)] font-bold">{yearly.toFixed(4)} ETH</span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">En 5 años (compuesto)</span>
            <span className="text-[var(--color-primary)] font-extrabold">{after5y.toFixed(4)} ETH</span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 17. AI Signal Card Widget ────────────────────────────────────────────────

function AiSignalCardWidget() {
  const [confidence, setConfidence] = useState(78);

  return (
    <WidgetShell title="AI Signal" icon={Activity}>
      <div className="space-y-3">
        <div>
          <label className="text-[10px] text-[var(--color-text-muted)] font-bold uppercase">Confianza: {confidence}%</label>
          <input type="range" min="20" max="95" value={confidence} onChange={(e) => setConfidence(parseInt(e.target.value))} className="w-full mt-1" />
        </div>

        {/* Signal card (replica real Alvora AI signal) */}
        <div className="p-3 rounded-xl" style={{ background: "var(--color-surface-2)", border: `1px solid ${confidence >= 70 ? "var(--color-success)" : confidence >= 50 ? "var(--color-warning)" : "var(--color-danger)"}` }}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[14px] font-bold" style={{ background: "var(--color-warning)", color: "white" }}>₿</div>
              <div>
                <div className="text-[13px] font-bold text-[var(--color-text)]">BTC/USDT</div>
                <div className="text-[10px] text-[var(--color-text-muted)]">Long · 1h</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[18px] font-extrabold" style={{ color: confidence >= 70 ? "var(--color-success)" : confidence >= 50 ? "var(--color-warning)" : "var(--color-danger)" }}>
                {confidence}%
              </div>
              <div className="text-[8px] text-[var(--color-text-muted)] uppercase font-bold">Confianza</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-[10px]">
            <div className="text-center p-1.5 rounded bg-[var(--color-surface)]">
              <div className="text-[var(--color-text-muted)] font-bold">Entry</div>
              <div className="text-[var(--color-text)] font-bold">$49,500</div>
            </div>
            <div className="text-center p-1.5 rounded bg-[var(--color-surface)]">
              <div className="text-[var(--color-danger)] font-bold">Stop</div>
              <div className="text-[var(--color-text)] font-bold">$48,000</div>
            </div>
            <div className="text-center p-1.5 rounded bg-[var(--color-surface)]">
              <div className="text-[var(--color-success)] font-bold">Target</div>
              <div className="text-[var(--color-text)] font-bold">$53,000</div>
            </div>
          </div>

          <div className="mt-2 p-2 rounded-lg text-[10px] text-[var(--color-text-muted)]" style={{ background: "var(--color-surface)" }}>
            RSI sobrevendido + divergencia alcista + acumulación whale + funding negativo
          </div>
        </div>

        <div className="p-2.5 rounded-lg text-[11px]" style={{ background: "var(--color-surface-2)" }}>
          <span className="text-[var(--color-text-muted)]">
            {confidence >= 70 ? "Alta confianza — considera ejecutar con 2% risk" : confidence >= 50 ? "Confianza moderada — usa confirmación adicional" : "Confianza baja — no operar solo por esta señal"}
          </span>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 18. Market Regime Widget ─────────────────────────────────────────────────

function MarketRegimeWidget() {
  const [regime, setRegime] = useState<"trend" | "range" | "crisis">("range");

  const configs = {
    trend: { label: "Trending", color: "var(--color-success)", icon: "📈", adx: "ADX > 25", strategy: "Trend following, MA crossover", bot: "DCA Bot ✓" },
    range: { label: "Ranging", color: "var(--color-primary)", icon: "↔️", adx: "ADX < 20", strategy: "Grid trading, mean reversion", bot: "Grid Bot ✓" },
    crisis: { label: "Crisis", color: "var(--color-danger)", icon: "📉", adx: "VIX > 40", strategy: "Reduce exposición, stablecoins", bot: "Pausar bots" },
  };

  const cfg = configs[regime];

  return (
    <WidgetShell title="Market Regime Detector" icon={Activity}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-1.5">
          {(Object.keys(configs) as ("trend" | "range" | "crisis")[]).map((k) => (
            <button
              key={k}
              onClick={() => setRegime(k)}
              className="p-2 rounded-lg text-center transition-all"
              style={{
                background: regime === k ? `color-mix(in srgb, ${configs[k].color} 12%, var(--color-surface))` : "var(--color-surface-2)",
                border: regime === k ? `2px solid ${configs[k].color}` : "1px solid var(--color-border)",
              }}
            >
              <div className="text-[18px]">{configs[k].icon}</div>
              <div className="text-[9px] font-bold mt-0.5" style={{ color: regime === k ? configs[k].color : "var(--color-text-muted)" }}>
                {configs[k].label}
              </div>
            </button>
          ))}
        </div>

        <div className="p-3 rounded-lg space-y-2 text-[12px]" style={{ background: "var(--color-surface-2)" }}>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Detector</span>
            <span className="font-bold" style={{ color: cfg.color }}>{cfg.adx}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">Estrategia</span>
            <span className="text-[var(--color-text)] font-bold">{cfg.strategy}</span>
          </div>
          <div className="flex justify-between pt-1.5 border-t border-[var(--color-border)]">
            <span className="text-[var(--color-text-muted)] font-bold">Bot recomendado</span>
            <span className="font-extrabold" style={{ color: cfg.color }}>{cfg.bot}</span>
          </div>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 19. Fibonacci Retracement Widget ─────────────────────────────────────────

function FibonacciRetracementWidget() {
  const fibLevels = [0, 23.6, 38.2, 50, 61.8, 78.6, 100];
  const swingLow = 40000;
  const swingHigh = 60000;
  const range = swingHigh - swingLow;

  return (
    <WidgetShell title="Fibonacci Retracement" icon={TrendingUp}>
      <div className="space-y-2">
        <div className="text-[10px] text-[var(--color-text-muted)] text-center">
          Swing: ${swingLow.toLocaleString()} → ${swingHigh.toLocaleString()}
        </div>
        {fibLevels.reverse().map((level) => {
          const price = swingHigh - (range * level) / 100;
          const isKey = level === 61.8 || level === 38.2;
          return (
            <div key={level} className="flex items-center gap-2">
              <span className="text-[10px] font-bold w-12" style={{ color: isKey ? "var(--color-warning)" : "var(--color-text-muted)" }}>
                {level}%
              </span>
              <div className="flex-1 h-6 rounded relative" style={{ background: "var(--color-surface-2)" }}>
                <div
                  className="absolute h-full rounded"
                  style={{
                    width: `${100 - level}%`,
                    background: isKey ? "color-mix(in srgb, var(--color-warning) 30%, transparent)" : "color-mix(in srgb, var(--color-primary) 15%, transparent)",
                  }}
                />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-bold text-[var(--color-text)]">
                  ${price.toFixed(0)}
                </span>
              </div>
            </div>
          );
        })}
        <div className="p-2.5 rounded-lg text-[11px]" style={{ background: "var(--color-surface-2)" }}>
          <span className="text-[var(--color-warning)] font-bold">61.8%</span>
          <span className="text-[var(--color-text-muted)]"> (Golden Ratio) es el nivel de retracement más importante. Actúa como soporte fuerte.</span>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── 20. Bollinger Bands Widget ───────────────────────────────────────────────

function BollingerBandsWidget() {
  const price = [48, 49, 50, 51, 50, 49, 48, 49, 50, 51, 52, 53, 55, 57, 60];
  const sma = price.map((_, i) => i < 4 ? price[i] : price.slice(i - 4, i + 1).reduce((a, b) => a + b, 0) / 5);
  const upper = sma.map((s) => s + 3);
  const lower = sma.map((s) => s - 3);
  const maxVal = Math.max(...upper);

  return (
    <WidgetShell title="Bollinger Bands" icon={Activity}>
      <div className="space-y-3">
        <div className="relative h-32 rounded-lg p-2" style={{ background: "var(--color-surface-2)" }}>
          <svg className="absolute inset-2" width="calc(100% - 16px)" height="calc(100% - 16px)" preserveAspectRatio="none">
            {/* Band fill */}
            <polygon
              points={[
                ...upper.map((v, i) => `${(i / (upper.length - 1)) * 100},${100 - (v / maxVal) * 90}`),
                ...lower.reverse().map((v, i) => `${100 - (i / (lower.length - 1)) * 100},${100 - (v / maxVal) * 90}`),
              ].join(" ")}
              fill="color-mix(in srgb, var(--color-primary) 10%, transparent)"
            />
            {/* Upper band */}
            <polyline points={upper.map((v, i) => `${(i / (upper.length - 1)) * 100},${100 - (v / maxVal) * 90}`).join(" ")} fill="none" stroke="var(--color-warning)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            {/* SMA */}
            <polyline points={sma.map((v, i) => `${(i / (sma.length - 1)) * 100},${100 - (v / maxVal) * 90}`).join(" ")} fill="none" stroke="var(--color-primary)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            {/* Lower band */}
            <polyline points={lower.map((v, i) => `${(i / (lower.length - 1)) * 100},${100 - (v / maxVal) * 90}`).join(" ")} fill="none" stroke="var(--color-warning)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            {/* Price */}
            <polyline points={price.map((v, i) => `${(i / (price.length - 1)) * 100},${100 - (v / maxVal) * 90}`).join(" ")} fill="none" stroke="var(--color-text)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </svg>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1"><div className="w-3 h-0.5" style={{ background: "var(--color-text)" }} /><span className="text-[var(--color-text-muted)]">Precio</span></span>
          <span className="flex items-center gap-1"><div className="w-3 h-0.5" style={{ background: "var(--color-primary)" }} /><span className="text-[var(--color-text-muted)]">SMA(20)</span></span>
          <span className="flex items-center gap-1"><div className="w-3 h-0.5" style={{ background: "var(--color-warning)" }} /><span className="text-[var(--color-text-muted)]">±2σ</span></span>
        </div>
        <div className="p-2.5 rounded-lg text-[11px]" style={{ background: "var(--color-surface-2)" }}>
          <span className="text-[var(--color-text-muted)]">Bandas estrechas = baja volatilidad (squeeze). Breakout inminente.</span>
        </div>
      </div>
    </WidgetShell>
  );
}

// ─── Dispatcher ────────────────────────────────────────────────────────────────

const WIDGET_MAP: Record<WidgetType, React.FC> = {
  "order-form": OrderFormWidget,
  "candlestick-patterns": CandlestickPatternsWidget,
  "support-resistance": SupportResistanceWidget,
  "moving-averages": MovingAveragesWidget,
  "rsi-macd": RsiMacdWidget,
  "volume-profile": VolumeProfileWidget,
  "grid-bot-viz": GridBotVizWidget,
  "dca-averaging": DcaAveragingWidget,
  "position-sizing": PositionSizingWidget,
  "correlation-matrix": CorrelationMatrixWidget,
  "fibonacci-retracement": FibonacciRetracementWidget,
  "bollinger-bands": BollingerBandsWidget,
  "tax-calculator": TaxCalculatorWidget,
  "wallet-safety": WalletSafetyWidget,
  "staking-calculator": StakingCalculatorWidget,
  "ai-signal-card": AiSignalCardWidget,
  "market-regime": MarketRegimeWidget,
  "risk-reward": RiskRewardWidget,
  "leverage-calculator": LeverageCalculatorWidget,
  "sl-tp-visualizer": SlTpVisualizerWidget,
};

export function AcademyWidget({ type }: { type: WidgetType }) {
  const Component = WIDGET_MAP[type];
  if (!Component) return null;
  return <Component />;
}
