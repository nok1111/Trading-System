import { useState, useCallback } from "react";
import { PriceChart } from "../components/charts/PriceChart";
import { DrawingToolbar, type DrawingTool } from "../components/charts/DrawingToolbar";
import { MultiChartLayout } from "../components/charts/MultiChartLayout";
import { IndicatorPicker } from "../components/charts/IndicatorPicker";
import { clearDrawings } from "../lib/chartStorage";
import { Layout, PanelsTopLeft, BarChart3 } from "lucide-react";

type ViewMode = "single" | "multi";

export function ChartStudioPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("single");
  const [activeTool, setActiveTool] = useState<DrawingTool>("none");
  const [drawColor, setDrawColor] = useState("#7c3aed");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("1h");
  const [showIndicatorPicker, setShowIndicatorPicker] = useState(false);

  // ─── Drawing management ─────────────────────────────────────────────────────
  const handleClearAll = useCallback(() => {
    clearDrawings(symbol);
    // Force chart re-render by toggling a state
    setSymbol((s) => s + " " ? s.trim() : s);
  }, [symbol]);

  // ─── Indicator toggle handler ───────────────────────────────────────────────
  const handleIndicatorToggle = useCallback(
    (name: string, enabled: boolean, _params: Record<string, number | string>, _color: string) => {
      // In a full implementation, this would pass indicator settings to PriceChart
      // For now, we just track the state. The PriceChart component has its own
      // built-in indicator toggles that work independently.
      console.log(`Indicator ${name} ${enabled ? "enabled" : "disabled"}`);
    },
    [],
  );

  return (
    <div className="p-5 space-y-4 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-[var(--color-primary)]/15">
            <BarChart3 size={20} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h1 className="text-[18px] font-extrabold text-[var(--color-text)]">Chart Studio</h1>
            <p className="text-[12px] text-[var(--color-text-muted)]">
              Advanced charting with drawing tools, multi-chart layout, and indicators
            </p>
          </div>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setViewMode("single")}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-bold transition-colors ${
              viewMode === "single"
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <Layout size={14} />
            Single Chart
          </button>
          <button
            onClick={() => setViewMode("multi")}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-bold transition-colors ${
              viewMode === "multi"
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <PanelsTopLeft size={14} />
            Multi-Chart
          </button>
        </div>
      </div>

      {/* Drawing toolbar (only for single chart mode) */}
      {viewMode === "single" && (
        <DrawingToolbar
          activeTool={activeTool}
          onToolChange={setActiveTool}
          color={drawColor}
          onColorChange={setDrawColor}
          onClearAll={handleClearAll}
        />
      )}

      {/* Main layout: chart area + indicator picker sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
        {/* Chart area */}
        <div className="space-y-3">
          {viewMode === "single" ? (
            <div className="panel p-4">
              {/* Symbol & interval selectors for single chart */}
              <div className="flex items-center gap-2 mb-3">
                <select
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="px-3 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[13px] font-bold text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  {["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"].map(
                    (s) => (
                      <option key={s} value={s}>
                        {s.replace("USDT", "/USDT")}
                      </option>
                    ),
                  )}
                </select>
                <select
                  value={interval}
                  onChange={(e) => setInterval(e.target.value)}
                  className="px-3 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[13px] font-bold text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  {["5m", "15m", "1h", "4h", "1d"].map((tf) => (
                    <option key={tf} value={tf}>
                      {tf}
                    </option>
                  ))}
                </select>
                {activeTool !== "none" && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--color-primary)]/15 text-[var(--color-primary)] text-[11px] font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" />
                    {activeTool} active — click on chart to draw
                  </div>
                )}
              </div>
              <PriceChart symbol={symbol} interval={interval} height={550} />
            </div>
          ) : (
            <MultiChartLayout defaultSymbol={symbol} defaultInterval={interval} />
          )}
        </div>

        {/* Sidebar: Indicator picker */}
        <div className="space-y-3">
          <button
            onClick={() => setShowIndicatorPicker(!showIndicatorPicker)}
            className="w-full flex items-center justify-between p-3 panel hover:bg-[var(--color-surface-2)] transition-colors lg:hidden"
          >
            <span className="text-[13px] font-bold text-[var(--color-text)]">Indicators</span>
            <span className="text-[var(--color-text-muted)] text-[12px]">
              {showIndicatorPicker ? "Hide" : "Show"}
            </span>
          </button>
          <div className={showIndicatorPicker ? "block" : "hidden lg:block"}>
            <IndicatorPicker onToggle={handleIndicatorToggle} />
          </div>
        </div>
      </div>
    </div>
  );
}
