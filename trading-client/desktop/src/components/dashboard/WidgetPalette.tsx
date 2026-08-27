import {
  Wallet,
  CandlestickChart,
  Zap,
  Activity,
  Fish,
  Table,
  MessageSquare,
  Bot,
  Newspaper,
  Shield,
  type LucideIcon,
} from "lucide-react";

export type WidgetType =
  | "PortfolioHero"
  | "PriceChart"
  | "SignalFeed"
  | "FearGreedGauge"
  | "WhaleFeed"
  | "PositionsTable"
  | "AlvoraChat"
  | "BotStatus"
  | "NewsFeed"
  | "NetExposure";

export interface WidgetMeta {
  type: WidgetType;
  label: string;
  icon: LucideIcon;
  description: string;
  defaultSpan?: number;
}

export const WIDGET_REGISTRY: WidgetMeta[] = [
  {
    type: "PortfolioHero",
    label: "Portfolio Hero",
    icon: Wallet,
    description: "Total equity, P&L, and allocation overview",
    defaultSpan: 2,
  },
  {
    type: "PriceChart",
    label: "Price Chart",
    icon: CandlestickChart,
    description: "Candlestick chart with indicators",
    defaultSpan: 2,
  },
  {
    type: "SignalFeed",
    label: "Signal Feed",
    icon: Zap,
    description: "Live trading signals from AI analysis",
    defaultSpan: 1,
  },
  {
    type: "FearGreedGauge",
    label: "Fear & Greed",
    icon: Activity,
    description: "Market sentiment gauge",
    defaultSpan: 1,
  },
  {
    type: "WhaleFeed",
    label: "Whale Feed",
    icon: Fish,
    description: "Large on-chain whale transactions",
    defaultSpan: 1,
  },
  {
    type: "PositionsTable",
    label: "Positions",
    icon: Table,
    description: "Open positions across all brokers",
    defaultSpan: 2,
  },
  {
    type: "AlvoraChat",
    label: "Alvora Chat",
    icon: MessageSquare,
    description: "AI copilot chat interface",
    defaultSpan: 1,
  },
  {
    type: "BotStatus",
    label: "Bot Status",
    icon: Bot,
    description: "Grid & DCA bot monitoring",
    defaultSpan: 1,
  },
  {
    type: "NewsFeed",
    label: "News Feed",
    icon: Newspaper,
    description: "Latest crypto news and events",
    defaultSpan: 1,
  },
  {
    type: "NetExposure",
    label: "Net Exposure",
    icon: Shield,
    description: "Net exposure per asset across brokers",
    defaultSpan: 1,
  },
];

export function getWidgetMeta(type: WidgetType): WidgetMeta | undefined {
  return WIDGET_REGISTRY.find((w) => w.type === type);
}

interface WidgetPaletteProps {
  onAdd: (type: WidgetType) => void;
  activeTypes: WidgetType[];
}

export function WidgetPalette({ onAdd, activeTypes }: WidgetPaletteProps) {
  return (
    <div className="panel p-4">
      <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Add Widget</h3>
      <div className="grid grid-cols-2 gap-2">
        {WIDGET_REGISTRY.map((w) => {
          const Icon = w.icon;
          const isActive = activeTypes.includes(w.type);
          return (
            <button
              key={w.type}
              onClick={() => onAdd(w.type)}
              disabled={isActive}
              className={`flex flex-col items-start gap-1 p-3 rounded-lg border text-left transition-all ${
                isActive
                  ? "border-[var(--color-border)] opacity-40 cursor-not-allowed"
                  : "border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-surface-2)] cursor-pointer"
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon size={16} className="text-[var(--color-primary)]" />
                <span className="text-[12px] font-bold text-[var(--color-text)]">{w.label}</span>
              </div>
              <span className="text-[10px] text-[var(--color-text-muted)] leading-tight">{w.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
