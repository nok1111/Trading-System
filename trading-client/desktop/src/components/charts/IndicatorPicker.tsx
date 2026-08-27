import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Settings2 } from "lucide-react";
import { saveIndicatorSettings, loadIndicatorSettings, type IndicatorSettings } from "../../lib/chartStorage";

// ─── Indicator definitions ────────────────────────────────────────────────────

export interface IndicatorDef {
  name: string;
  label: string;
  category: string;
  description: string;
  defaultParams: Record<string, number | string>;
  defaultColor: string;
  paramDefs: { key: string; label: string; type: "number" | "select"; min?: number; max?: number; step?: number; options?: string[]; default: number | string; unit?: string }[];
}

export const AVAILABLE_INDICATORS: IndicatorDef[] = [
  // ─── Existing (already in PriceChart) ───────────────────────────────────────
  {
    name: "ema",
    label: "EMA",
    category: "Trend",
    description: "Exponential Moving Average",
    defaultParams: { period: 20 },
    defaultColor: "#f59e0b",
    paramDefs: [
      { key: "period", label: "Period", type: "number", min: 2, max: 200, step: 1, default: 20 },
    ],
  },
  {
    name: "bollinger",
    label: "Bollinger Bands",
    category: "Volatility",
    description: "Bollinger Bands with configurable std dev",
    defaultParams: { period: 20, stdDev: 2 },
    defaultColor: "#7c3aed",
    paramDefs: [
      { key: "period", label: "Period", type: "number", min: 5, max: 100, step: 1, default: 20 },
      { key: "stdDev", label: "Std Dev", type: "number", min: 0.5, max: 5, step: 0.5, default: 2 },
    ],
  },
  {
    name: "rsi",
    label: "RSI",
    category: "Momentum",
    description: "Relative Strength Index",
    defaultParams: { period: 14 },
    defaultColor: "#f59e0b",
    paramDefs: [
      { key: "period", label: "Period", type: "number", min: 2, max: 50, step: 1, default: 14 },
    ],
  },
  {
    name: "macd",
    label: "MACD",
    category: "Momentum",
    description: "Moving Average Convergence Divergence",
    defaultParams: { fast: 12, slow: 26, signal: 9 },
    defaultColor: "#7c3aed",
    paramDefs: [
      { key: "fast", label: "Fast", type: "number", min: 2, max: 50, step: 1, default: 12 },
      { key: "slow", label: "Slow", type: "number", min: 5, max: 100, step: 1, default: 26 },
      { key: "signal", label: "Signal", type: "number", min: 2, max: 50, step: 1, default: 9 },
    ],
  },

  // ─── New advanced indicators ────────────────────────────────────────────────
  {
    name: "vwap",
    label: "VWAP",
    category: "Volume",
    description: "Volume Weighted Average Price",
    defaultParams: { anchor: "session" },
    defaultColor: "#3b82f6",
    paramDefs: [
      { key: "anchor", label: "Anchor", type: "select", options: ["session", "week", "month"], default: "session" },
    ],
  },
  {
    name: "ichimoku",
    label: "Ichimoku Cloud",
    category: "Trend",
    description: "Ichimoku Kinko Hyo — support, resistance, and momentum",
    defaultParams: { conversion: 9, base: 26, span: 52 },
    defaultColor: "#22d39a",
    paramDefs: [
      { key: "conversion", label: "Conversion", type: "number", min: 2, max: 50, step: 1, default: 9 },
      { key: "base", label: "Base", type: "number", min: 5, max: 100, step: 1, default: 26 },
      { key: "span", label: "Span", type: "number", min: 10, max: 200, step: 1, default: 52 },
    ],
  },
  {
    name: "stochastic",
    label: "Stochastic",
    category: "Momentum",
    description: "Stochastic Oscillator (%K and %D)",
    defaultParams: { kPeriod: 14, dPeriod: 3, smooth: 3 },
    defaultColor: "#ec4899",
    paramDefs: [
      { key: "kPeriod", label: "%K Period", type: "number", min: 2, max: 50, step: 1, default: 14 },
      { key: "dPeriod", label: "%D Period", type: "number", min: 1, max: 20, step: 1, default: 3 },
      { key: "smooth", label: "Smooth", type: "number", min: 1, max: 10, step: 1, default: 3 },
    ],
  },
  {
    name: "adx",
    label: "ADX",
    category: "Trend",
    description: "Average Directional Index — trend strength",
    defaultParams: { period: 14 },
    defaultColor: "#a855f7",
    paramDefs: [
      { key: "period", label: "Period", type: "number", min: 5, max: 50, step: 1, default: 14 },
    ],
  },
  {
    name: "atr",
    label: "ATR",
    category: "Volatility",
    description: "Average True Range — volatility measure",
    defaultParams: { period: 14 },
    defaultColor: "#ff5f6d",
    paramDefs: [
      { key: "period", label: "Period", type: "number", min: 5, max: 50, step: 1, default: 14 },
    ],
  },
  {
    name: "obv",
    label: "OBV",
    category: "Volume",
    description: "On Balance Volume — cumulative volume flow",
    defaultParams: {},
    defaultColor: "#3b82f6",
    paramDefs: [],
  },
];

// ─── Component ────────────────────────────────────────────────────────────────

interface IndicatorPickerProps {
  onToggle: (name: string, enabled: boolean, params: Record<string, number | string>, color: string) => void;
}

export function IndicatorPicker({ onToggle }: IndicatorPickerProps) {
  const [settings, setSettings] = useState<IndicatorSettings>({});
  const [expandedIndicator, setExpandedIndicator] = useState<string | null>(null);

  // Load saved settings on mount
  useEffect(() => {
    const saved = loadIndicatorSettings();
    if (saved) {
      setSettings(saved);
      // Notify parent of initial state
      for (const [name, s] of Object.entries(saved)) {
        if (s.enabled) {
          const def = AVAILABLE_INDICATORS.find((i) => i.name === name);
          onToggle(name, true, s.params, s.color || def?.defaultColor || "#7c3aed");
        }
      }
    }
  }, []);

  const updateSettings = (next: IndicatorSettings) => {
    setSettings(next);
    saveIndicatorSettings(next);
  };

  const handleToggle = (name: string) => {
    const def = AVAILABLE_INDICATORS.find((i) => i.name === name);
    if (!def) return;
    const current = settings[name];
    const enabled = !current?.enabled;
    const params = current?.params || def.defaultParams;
    const color = current?.color || def.defaultColor;

    updateSettings({ ...settings, [name]: { enabled, params, color } });
    onToggle(name, enabled, params, color);
  };

  const handleParamChange = (name: string, key: string, value: number | string) => {
    const current = settings[name];
    if (!current) return;
    const params = { ...current.params, [key]: value };
    updateSettings({ ...settings, [name]: { ...current, params } });
    if (current.enabled) {
      onToggle(name, true, params, current.color || "");
    }
  };

  const handleColorChange = (name: string, color: string) => {
    const current = settings[name];
    if (!current) return;
    updateSettings({ ...settings, [name]: { ...current, color } });
    if (current.enabled) {
      onToggle(name, true, current.params, color);
    }
  };

  // Group by category
  const categories = [...new Set(AVAILABLE_INDICATORS.map((i) => i.category))];

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Settings2 size={16} className="text-[var(--color-primary)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Indicators</h3>
      </div>

      <div className="space-y-4">
        {categories.map((cat) => (
          <div key={cat}>
            <h4 className="text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              {cat}
            </h4>
            <div className="space-y-1">
              {AVAILABLE_INDICATORS.filter((i) => i.category === cat).map((indicator) => {
                const s = settings[indicator.name];
                const enabled = s?.enabled || false;
                const isExpanded = expandedIndicator === indicator.name;

                return (
                  <div key={indicator.name}>
                    <div className="flex items-center gap-2">
                      {/* Toggle */}
                      <button
                        onClick={() => handleToggle(indicator.name)}
                        className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${
                          enabled ? "bg-[var(--color-primary)]" : "bg-[var(--color-surface-2)]"
                        }`}
                      >
                        <span
                          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                            enabled ? "translate-x-4" : "translate-x-0.5"
                          }`}
                        />
                      </button>

                      {/* Label */}
                      <span className="text-[12px] font-bold text-[var(--color-text)] flex-1">
                        {indicator.label}
                      </span>

                      {/* Color */}
                      <input
                        type="color"
                        value={s?.color || indicator.defaultColor}
                        onChange={(e) => handleColorChange(indicator.name, e.target.value)}
                        className="w-5 h-5 rounded cursor-pointer bg-transparent border border-[var(--color-border)]"
                        title="Indicator color"
                      />

                      {/* Expand settings */}
                      {indicator.paramDefs.length > 0 && (
                        <button
                          onClick={() => setExpandedIndicator(isExpanded ? null : indicator.name)}
                          className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-0.5"
                        >
                          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      )}
                    </div>

                    {/* Settings panel */}
                    {isExpanded && indicator.paramDefs.length > 0 && (
                      <div className="ml-9 mt-1.5 space-y-2 pb-1">
                        {indicator.paramDefs.map((param) => (
                          <div key={param.key} className="flex items-center gap-2">
                            <label className="text-[11px] text-[var(--color-text-muted)] w-20">
                              {param.label}
                            </label>
                            {param.type === "select" ? (
                              <select
                                value={String(s?.params?.[param.key] ?? param.default)}
                                onChange={(e) => handleParamChange(indicator.name, param.key, e.target.value)}
                                className="flex-1 px-2 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                              >
                                {param.options?.map((opt) => (
                                  <option key={opt} value={opt}>{opt}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type="number"
                                value={Number(s?.params?.[param.key] ?? param.default)}
                                min={param.min}
                                max={param.max}
                                step={param.step}
                                onChange={(e) =>
                                  handleParamChange(indicator.name, param.key, parseFloat(e.target.value) || 0)
                                }
                                className="flex-1 px-2 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[11px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)] w-16"
                              />
                            )}
                            {param.unit && (
                              <span className="text-[10px] text-[var(--color-text-muted)]">{param.unit}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
