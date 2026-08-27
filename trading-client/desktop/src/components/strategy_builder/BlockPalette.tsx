import {
  TrendingUp,
  TrendingDown,
  Target,
  Shield,
  DollarSign,
  Percent,
  Brain,
  Clock,
  AlertTriangle,
  BarChart3,
  type LucideIcon,
} from "lucide-react";

// ─── Block type definitions ───────────────────────────────────────────────────

export type BlockCategory = "entry" | "exit" | "sizing" | "risk";

export interface BlockTypeDef {
  type: string;
  category: BlockCategory;
  label: string;
  icon: LucideIcon;
  description: string;
  defaultParams: Record<string, number | string | boolean>;
  paramDefs: ParamDef[];
}

export interface ParamDef {
  key: string;
  label: string;
  type: "number" | "select" | "boolean";
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  default: number | string | boolean;
  unit?: string;
}

// ─── Block definitions ────────────────────────────────────────────────────────

export const BLOCK_DEFINITIONS: BlockTypeDef[] = [
  // ─── Entry blocks ──────────────────────────────────────────────────────────
  {
    type: "entry_price_above",
    category: "entry",
    label: "Price Above",
    icon: TrendingUp,
    description: "Enter when price rises above a threshold",
    defaultParams: { threshold_pct: 2, lookback: 20 },
    paramDefs: [
      { key: "threshold_pct", label: "Threshold %", type: "number", min: 0.1, max: 20, step: 0.1, default: 2, unit: "%" },
      { key: "lookback", label: "Lookback Period", type: "number", min: 1, max: 200, step: 1, default: 20 },
    ],
  },
  {
    type: "entry_price_below",
    category: "entry",
    label: "Price Below",
    icon: TrendingDown,
    description: "Enter when price falls below a threshold",
    defaultParams: { threshold_pct: 2, lookback: 20 },
    paramDefs: [
      { key: "threshold_pct", label: "Threshold %", type: "number", min: 0.1, max: 20, step: 0.1, default: 2, unit: "%" },
      { key: "lookback", label: "Lookback Period", type: "number", min: 1, max: 200, step: 1, default: 20 },
    ],
  },
  {
    type: "entry_rsi_level",
    category: "entry",
    label: "RSI Level",
    icon: Activity,
    description: "Enter when RSI crosses a level",
    defaultParams: { rsi_period: 14, rsi_level: 30, direction: "oversold" },
    paramDefs: [
      { key: "rsi_period", label: "RSI Period", type: "number", min: 2, max: 50, step: 1, default: 14 },
      { key: "rsi_level", label: "RSI Level", type: "number", min: 1, max: 99, step: 1, default: 30 },
      { key: "direction", label: "Direction", type: "select", options: ["oversold", "overbought"], default: "oversold" },
    ],
  },
  {
    type: "entry_ma_cross",
    category: "entry",
    label: "MA Cross",
    icon: BarChart3,
    description: "Enter on moving average crossover",
    defaultParams: { fast_period: 9, slow_period: 21, ma_type: "ema" },
    paramDefs: [
      { key: "fast_period", label: "Fast Period", type: "number", min: 2, max: 100, step: 1, default: 9 },
      { key: "slow_period", label: "Slow Period", type: "number", min: 5, max: 200, step: 1, default: 21 },
      { key: "ma_type", label: "MA Type", type: "select", options: ["ema", "sma"], default: "ema" },
    ],
  },
  {
    type: "entry_volume_spike",
    category: "entry",
    label: "Volume Spike",
    icon: BarChart3,
    description: "Enter on volume spike above average",
    defaultParams: { multiplier: 2, lookback: 20 },
    paramDefs: [
      { key: "multiplier", label: "Volume Multiplier", type: "number", min: 1, max: 10, step: 0.1, default: 2, unit: "x" },
      { key: "lookback", label: "Lookback Period", type: "number", min: 5, max: 100, step: 1, default: 20 },
    ],
  },
  {
    type: "entry_ai_signal",
    category: "entry",
    label: "AI Signal",
    icon: Brain,
    description: "Enter based on AI copilot signal",
    defaultParams: { confidence: 70, signal_type: "buy" },
    paramDefs: [
      { key: "confidence", label: "Min Confidence", type: "number", min: 50, max: 100, step: 1, default: 70, unit: "%" },
      { key: "signal_type", label: "Signal Type", type: "select", options: ["buy", "sell"], default: "buy" },
    ],
  },

  // ─── Exit blocks ───────────────────────────────────────────────────────────
  {
    type: "exit_take_profit",
    category: "exit",
    label: "Take Profit",
    icon: Target,
    description: "Exit at target profit percentage",
    defaultParams: { tp_pct: 5 },
    paramDefs: [
      { key: "tp_pct", label: "Take Profit %", type: "number", min: 0.5, max: 50, step: 0.5, default: 5, unit: "%" },
    ],
  },
  {
    type: "exit_stop_loss",
    category: "exit",
    label: "Stop Loss",
    icon: Shield,
    description: "Exit at stop loss percentage",
    defaultParams: { sl_pct: 3 },
    paramDefs: [
      { key: "sl_pct", label: "Stop Loss %", type: "number", min: 0.5, max: 50, step: 0.5, default: 3, unit: "%" },
    ],
  },
  {
    type: "exit_trailing_stop",
    category: "exit",
    label: "Trailing Stop",
    icon: Shield,
    description: "Dynamic trailing stop loss",
    defaultParams: { trail_pct: 2, activation_pct: 1 },
    paramDefs: [
      { key: "trail_pct", label: "Trail Distance %", type: "number", min: 0.5, max: 20, step: 0.5, default: 2, unit: "%" },
      { key: "activation_pct", label: "Activation %", type: "number", min: 0, max: 20, step: 0.5, default: 1, unit: "%" },
    ],
  },
  {
    type: "exit_time_exit",
    category: "exit",
    label: "Time Exit",
    icon: Clock,
    description: "Exit after a time period",
    defaultParams: { max_bars: 48 },
    paramDefs: [
      { key: "max_bars", label: "Max Bars", type: "number", min: 1, max: 500, step: 1, default: 48 },
    ],
  },

  // ─── Position sizing blocks ────────────────────────────────────────────────
  {
    type: "sizing_fixed_usd",
    category: "sizing",
    label: "Fixed USD",
    icon: DollarSign,
    description: "Fixed USD amount per trade",
    defaultParams: { amount: 100 },
    paramDefs: [
      { key: "amount", label: "Amount (USD)", type: "number", min: 1, max: 100000, step: 1, default: 100, unit: "$" },
    ],
  },
  {
    type: "sizing_pct_portfolio",
    category: "sizing",
    label: "% of Portfolio",
    icon: Percent,
    description: "Percentage of total portfolio",
    defaultParams: { pct: 5 },
    paramDefs: [
      { key: "pct", label: "Percentage", type: "number", min: 0.1, max: 100, step: 0.1, default: 5, unit: "%" },
    ],
  },
  {
    type: "sizing_kelly",
    category: "sizing",
    label: "Kelly Criterion",
    icon: Percent,
    description: "Kelly criterion position sizing",
    defaultParams: { kelly_fraction: 0.5, win_rate: 55, win_loss_ratio: 1.5 },
    paramDefs: [
      { key: "kelly_fraction", label: "Kelly Fraction", type: "number", min: 0.1, max: 1, step: 0.1, default: 0.5 },
      { key: "win_rate", label: "Win Rate %", type: "number", min: 1, max: 99, step: 1, default: 55, unit: "%" },
      { key: "win_loss_ratio", label: "Win/Loss Ratio", type: "number", min: 0.1, max: 10, step: 0.1, default: 1.5 },
    ],
  },

  // ─── Risk filter blocks ────────────────────────────────────────────────────
  {
    type: "risk_max_positions",
    category: "risk",
    label: "Max Positions",
    icon: AlertTriangle,
    description: "Limit maximum concurrent positions",
    defaultParams: { max_positions: 5 },
    paramDefs: [
      { key: "max_positions", label: "Max Positions", type: "number", min: 1, max: 50, step: 1, default: 5 },
    ],
  },
  {
    type: "risk_max_drawdown",
    category: "risk",
    label: "Max Drawdown",
    icon: AlertTriangle,
    description: "Stop trading at max drawdown",
    defaultParams: { max_dd_pct: 15 },
    paramDefs: [
      { key: "max_dd_pct", label: "Max Drawdown %", type: "number", min: 1, max: 50, step: 1, default: 15, unit: "%" },
    ],
  },
  {
    type: "risk_regime_filter",
    category: "risk",
    label: "Market Regime",
    icon: BarChart3,
    description: "Only trade in specific market regime",
    defaultParams: { regime: "trending" },
    paramDefs: [
      { key: "regime", label: "Regime", type: "select", options: ["trending", "ranging", "volatile", "any"], default: "trending" },
    ],
  },
];

export function getBlockDef(type: string): BlockTypeDef | undefined {
  return BLOCK_DEFINITIONS.find((b) => b.type === type);
}

export const CATEGORY_LABELS: Record<BlockCategory, string> = {
  entry: "Entry",
  exit: "Exit",
  sizing: "Position Sizing",
  risk: "Risk Filters",
};

export const CATEGORY_COLORS: Record<BlockCategory, string> = {
  entry: "var(--color-success)",
  exit: "var(--color-danger)",
  sizing: "var(--color-primary)",
  risk: "var(--color-warning)",
};

// Import Activity icon for RSI block
import { Activity } from "lucide-react";

// ─── Palette component ────────────────────────────────────────────────────────

interface BlockPaletteProps {
  onAddBlock: (type: string) => void;
}

export function BlockPalette({ onAddBlock }: BlockPaletteProps) {
  const categories: BlockCategory[] = ["entry", "exit", "sizing", "risk"];

  return (
    <div className="panel p-4 overflow-y-auto" style={{ maxHeight: "70vh" }}>
      <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Block Palette</h3>
      <div className="space-y-4">
        {categories.map((cat) => {
          const blocks = BLOCK_DEFINITIONS.filter((b) => b.category === cat);
          return (
            <div key={cat}>
              <h4
                className="text-[11px] font-bold uppercase tracking-wide mb-2"
                style={{ color: CATEGORY_COLORS[cat] }}
              >
                {CATEGORY_LABELS[cat]}
              </h4>
              <div className="space-y-1.5">
                {blocks.map((block) => {
                  const Icon = block.icon;
                  return (
                    <button
                      key={block.type}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData("blockType", block.type);
                        e.dataTransfer.effectAllowed = "copy";
                      }}
                      onClick={() => onAddBlock(block.type)}
                      className="w-full flex items-center gap-2 p-2.5 rounded-lg border border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-surface-2)] cursor-grab active:cursor-grabbing transition-all text-left group"
                    >
                      <Icon size={16} className="flex-shrink-0" style={{ color: CATEGORY_COLORS[cat] }} />
                      <div className="min-w-0 flex-1">
                        <div className="text-[12px] font-bold text-[var(--color-text)]">{block.label}</div>
                        <div className="text-[10px] text-[var(--color-text-muted)] leading-tight truncate">
                          {block.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
