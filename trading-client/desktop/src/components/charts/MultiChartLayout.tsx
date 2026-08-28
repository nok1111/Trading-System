import { useState, useEffect } from "react";
import { Grid2x2, Square, Rows2, Columns2, Link2, Link2Off } from "lucide-react";
import { PriceChart } from "./PriceChart";
import { loadChartLayout, saveChartLayout, type ChartLayoutConfig } from "../../lib/chartStorage";

export type ChartLayout = "1x1" | "2x1" | "1x2" | "2x2";

interface ChartPanel {
  id: number;
  symbol: string;
  interval: string;
}

interface MultiChartLayoutProps {
  defaultSymbol?: string;
  defaultInterval?: string;
}

const LAYOUT_OPTIONS: { value: ChartLayout; label: string; icon: typeof Grid2x2 }[] = [
  { value: "1x1", label: "1x1", icon: Square },
  { value: "2x1", label: "2x1", icon: Rows2 },
  { value: "1x2", label: "1x2", icon: Columns2 },
  { value: "2x2", label: "2x2", icon: Grid2x2 },
];

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"];
const INTERVALS = ["5m", "15m", "1h", "4h", "1d"];

function getPanelCount(layout: ChartLayout): number {
  switch (layout) {
    case "1x1": return 1;
    case "2x1": return 2;
    case "1x2": return 2;
    case "2x2": return 4;
    default: return 1;
  }
}

function getGridClass(layout: ChartLayout): string {
  switch (layout) {
    case "1x1": return "grid-cols-1 grid-rows-1";
    case "2x1": return "grid-cols-1 grid-rows-2";
    case "1x2": return "grid-cols-2 grid-rows-1";
    case "2x2": return "grid-cols-2 grid-rows-2";
    default: return "grid-cols-1 grid-rows-1";
  }
}

export function MultiChartLayout({ defaultSymbol = "BTCUSDT", defaultInterval = "1h" }: MultiChartLayoutProps) {
  const [layout, setLayout] = useState<ChartLayout>("1x1");
  const [syncCrosshair, setSyncCrosshair] = useState(false);
  const [panels, setPanels] = useState<ChartPanel[]>([
    { id: 0, symbol: defaultSymbol, interval: defaultInterval },
    { id: 1, symbol: "ETHUSDT", interval: defaultInterval },
    { id: 2, symbol: "SOLUSDT", interval: defaultInterval },
    { id: 3, symbol: "BNBUSDT", interval: defaultInterval },
  ]);

  // Load saved layout on mount
  useEffect(() => {
    const saved = loadChartLayout();
    if (saved) {
      setLayout(saved.layout);
      setSyncCrosshair(saved.syncCrosshair);
      if (saved.charts && saved.charts.length > 0) {
        setPanels((prev) =>
          prev.map((p, i) => ({
            ...p,
            symbol: saved.charts[i]?.symbol || p.symbol,
            interval: saved.charts[i]?.interval || p.interval,
          })),
        );
      }
    }
  }, []);

  // Save layout when it changes
  const handleLayoutChange = (newLayout: ChartLayout) => {
    setLayout(newLayout);
    const config: ChartLayoutConfig = {
      layout: newLayout,
      charts: panels.slice(0, getPanelCount(newLayout)).map((p) => ({ symbol: p.symbol, interval: p.interval })),
      syncCrosshair,
    };
    saveChartLayout(config);
  };

  const handlePanelChange = (id: number, field: "symbol" | "interval", value: string) => {
    setPanels((prev) => {
      const next = prev.map((p) => (p.id === id ? { ...p, [field]: value } : p));
      const config: ChartLayoutConfig = {
        layout,
        charts: next.slice(0, getPanelCount(layout)).map((p) => ({ symbol: p.symbol, interval: p.interval })),
        syncCrosshair,
      };
      saveChartLayout(config);
      return next;
    });
  };

  const handleSyncToggle = () => {
    const next = !syncCrosshair;
    setSyncCrosshair(next);
    const config: ChartLayoutConfig = {
      layout,
      charts: panels.slice(0, getPanelCount(layout)).map((p) => ({ symbol: p.symbol, interval: p.interval })),
      syncCrosshair: next,
    };
    saveChartLayout(config);
  };

  const panelCount = getPanelCount(layout);
  const visiblePanels = panels.slice(0, panelCount);

  return (
    <div className="space-y-3">
      {/* Layout controls */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-[12px] font-bold text-[var(--color-text-muted)] mr-1">Layout:</span>
          {LAYOUT_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            return (
              <button
                key={opt.value}
                onClick={() => handleLayoutChange(opt.value)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${
                  layout === opt.value
                    ? "bg-[var(--color-primary)] text-white"
                    : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                }`}
                title={opt.label}
              >
                <Icon size={14} />
                {opt.label}
              </button>
            );
          })}
        </div>

        {/* Sync crosshair toggle */}
        <button
          onClick={handleSyncToggle}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-bold transition-colors ${
            syncCrosshair
              ? "bg-[var(--color-primary)]/15 text-[var(--color-primary)]"
              : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
          title="Sync crosshair between charts"
        >
          {syncCrosshair ? <Link2 size={14} /> : <Link2Off size={14} />}
          Sync Crosshair
        </button>
      </div>

      {/* Chart grid */}
      <div className={`grid gap-3 ${getGridClass(layout)}`} style={{ minHeight: "300px" }}>
        {visiblePanels.map((panel) => (
          <div key={panel.id} className="panel p-3 flex flex-col min-h-0">
            {/* Panel header with symbol/interval selectors */}
            <div className="flex items-center gap-2 mb-2 flex-shrink-0">
              <select
                value={panel.symbol}
                onChange={(e) => handlePanelChange(panel.id, "symbol", e.target.value)}
                className="px-2 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>{s.replace("USDT", "/USDT")}</option>
                ))}
              </select>
              <select
                value={panel.interval}
                onChange={(e) => handlePanelChange(panel.id, "interval", e.target.value)}
                className="px-2 py-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              >
                {INTERVALS.map((tf) => (
                  <option key={tf} value={tf}>{tf}</option>
                ))}
              </select>
            </div>
            {/* Chart */}
            <div className="flex-1 min-h-0">
              <PriceChart
                symbol={panel.symbol}
                interval={panel.interval}
                height={layout === "1x1" ? 500 : layout === "2x2" ? 280 : 350}
                syncCrosshair={syncCrosshair}
                syncId="multi-chart-sync"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
