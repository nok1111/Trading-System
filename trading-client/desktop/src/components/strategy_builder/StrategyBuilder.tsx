import { useState, useCallback } from "react";
import { Save, Play, Download, CheckCircle2, AlertCircle } from "lucide-react";
import { BlockPalette, getBlockDef, type BlockCategory } from "./BlockPalette";
import { BlockCanvas, type StrategyBlock } from "./BlockCanvas";
import { BlockConfig } from "./BlockConfig";
import { api } from "../../lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface StrategyConfig {
  name: string;
  description: string;
  blocks: StrategyBlock[];
}

interface StrategyBuilderProps {
  onSave?: (config: StrategyConfig) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function StrategyBuilder({ onSave }: StrategyBuilderProps) {
  const [blocks, setBlocks] = useState<StrategyBlock[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [strategyName, setStrategyName] = useState("My Strategy");
  const [strategyDesc, setStrategyDesc] = useState("");
  const [backtestSymbol, setBacktestSymbol] = useState("BTCUSDT");
  const [backtestInterval, setBacktestInterval] = useState("1h");
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [backtesting, setBacktesting] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // ─── Block management ───────────────────────────────────────────────────────

  const addBlock = useCallback((type: string) => {
    const def = getBlockDef(type);
    if (!def) return;
    const newBlock: StrategyBlock = {
      id: `${type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      type,
      category: def.category as BlockCategory,
      params: { ...def.defaultParams },
    };
    setBlocks((prev) => [...prev, newBlock]);
    setSelectedId(newBlock.id);
  }, []);

  const removeBlock = useCallback((id: string) => {
    setBlocks((prev) => prev.filter((b) => b.id !== id));
    setSelectedId((prev) => (prev === id ? null : prev));
  }, []);

  const updateBlockParams = useCallback((id: string, params: Record<string, number | string | boolean>) => {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, params } : b)));
  }, []);

  const reorderBlocks = useCallback((fromIndex: number, toIndex: number) => {
    setBlocks((prev) => {
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  }, []);

  // ─── Export / Validate / Backtest ───────────────────────────────────────────

  const buildConfig = useCallback((): StrategyConfig => {
    return {
      name: strategyName,
      description: strategyDesc,
      blocks,
    };
  }, [strategyName, strategyDesc, blocks]);

  const validateConfig = useCallback((): string[] => {
    const errors: string[] = [];
    const hasEntry = blocks.some((b) => b.category === "entry");
    const hasExit = blocks.some((b) => b.category === "exit");
    const hasSizing = blocks.some((b) => b.category === "sizing");

    if (blocks.length === 0) errors.push("Strategy has no blocks");
    if (!hasEntry) errors.push("At least one Entry block is required");
    if (!hasExit) errors.push("At least one Exit block is required");
    if (!hasSizing) errors.push("A Position Sizing block is required");

    // Check for conflicting entries
    const entries = blocks.filter((b) => b.category === "entry");
    if (entries.length > 3) errors.push("Too many entry blocks (max 3 recommended)");

    return errors;
  }, [blocks]);

  const handleExport = () => {
    const config = buildConfig();
    const json = JSON.stringify(config, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${strategyName.replace(/\s+/g, "_").toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSave = async () => {
    const errors = validateConfig();
    setValidationErrors(errors);
    if (errors.length > 0) {
      setSaveStatus("error");
      return;
    }

    const config = buildConfig();
    try {
      // Save strategy to backend
      await api("/api/strategy/save", {
        method: "POST",
        body: JSON.stringify(config),
      });
      setSaveStatus("saved");
      onSave?.(config);
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch {
      // Even if backend isn't available, call onSave callback
      onSave?.(config);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 3000);
    }
  };

  const handleBacktest = async () => {
    const errors = validateConfig();
    setValidationErrors(errors);
    if (errors.length > 0) return;

    setBacktesting(true);
    setBacktestResult(null);
    try {
      const config = buildConfig();
      const result = await api("/api/strategy/backtest", {
        method: "POST",
        body: JSON.stringify({
          config,
          symbol: backtestSymbol,
          interval: backtestInterval,
          limit: 500,
        }),
      });
      setBacktestResult(result);
    } catch (err: any) {
      setBacktestResult({ error: err.message || "Backtest failed" });
    } finally {
      setBacktesting(false);
    }
  };

  const selectedBlock = blocks.find((b) => b.id === selectedId) || null;

  // ─── Summary stats ──────────────────────────────────────────────────────────
  const entryCount = blocks.filter((b) => b.category === "entry").length;
  const exitCount = blocks.filter((b) => b.category === "exit").length;
  const sizingCount = blocks.filter((b) => b.category === "sizing").length;
  const riskCount = blocks.filter((b) => b.category === "risk").length;

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto p-5">
      {/* Header */}
      <div className="panel p-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              placeholder="Strategy name"
              className="w-full bg-transparent text-[18px] font-extrabold text-[var(--color-text)] focus:outline-none border-b border-transparent focus:border-[var(--color-primary)] pb-1"
            />
            <input
              type="text"
              value={strategyDesc}
              onChange={(e) => setStrategyDesc(e.target.value)}
              placeholder="Add a description..."
              className="w-full mt-1 bg-transparent text-[12px] text-[var(--color-text-muted)] focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)] hover:bg-[var(--color-surface-2)] transition-colors"
              title="Export to JSON"
            >
              <Download size={14} />
              Export
            </button>
            <button
              onClick={handleSave}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-bold transition-colors ${
                saveStatus === "saved"
                  ? "bg-[var(--color-success)]/15 text-[var(--color-success)]"
                  : saveStatus === "error"
                  ? "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
                  : "bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90"
              }`}
            >
              {saveStatus === "saved" ? <CheckCircle2 size={14} /> : <Save size={14} />}
              {saveStatus === "saved" ? "Saved!" : "Save"}
            </button>
          </div>
        </div>

        {/* Block summary */}
        <div className="flex items-center gap-4 mt-3 text-[11px]">
          <span className="text-[var(--color-success)] font-bold">{entryCount} Entry</span>
          <span className="text-[var(--color-danger)] font-bold">{exitCount} Exit</span>
          <span className="text-[var(--color-primary)] font-bold">{sizingCount} Sizing</span>
          <span className="text-[var(--color-warning)] font-bold">{riskCount} Risk</span>
          <span className="text-[var(--color-text-muted)]">{blocks.length} total blocks</span>
        </div>

        {/* Validation errors */}
        {validationErrors.length > 0 && (
          <div className="mt-3 space-y-1">
            {validationErrors.map((err, i) => (
              <div key={i} className="flex items-center gap-2 text-[12px] text-[var(--color-danger)]">
                <AlertCircle size={12} />
                {err}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main layout: palette | canvas | config */}
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr_280px] gap-4">
        {/* Left: Block palette */}
        <BlockPalette onAddBlock={addBlock} />

        {/* Center: Canvas */}
        <div className="space-y-3">
          <BlockCanvas
            blocks={blocks}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onRemove={removeBlock}
            onAddBlock={addBlock}
            onReorder={reorderBlocks}
          />

          {/* Backtest bar */}
          <div className="panel p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[12px] font-bold text-[var(--color-text-muted)]">Backtest:</span>
              <input
                type="text"
                value={backtestSymbol}
                onChange={(e) => setBacktestSymbol(e.target.value.toUpperCase())}
                placeholder="BTCUSDT"
                className="w-28 px-2 py-1.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              />
              <select
                value={backtestInterval}
                onChange={(e) => setBacktestInterval(e.target.value)}
                className="px-2 py-1.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
              >
                {["5m", "15m", "1h", "4h", "1d"].map((tf) => (
                  <option key={tf} value={tf}>{tf}</option>
                ))}
              </select>
              <button
                onClick={handleBacktest}
                disabled={backtesting || blocks.length === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-primary)] text-white text-[12px] font-bold hover:bg-[var(--color-primary)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Play size={12} />
                {backtesting ? "Running..." : "Preview Backtest"}
              </button>
            </div>

            {/* Backtest results */}
            {backtestResult && (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                {backtestResult.error ? (
                  <div className="text-[12px] text-[var(--color-danger)]">{backtestResult.error}</div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div>
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Total Return</div>
                      <div className={`text-[16px] font-bold ${backtestResult.total_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                        {backtestResult.total_return_pct?.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Win Rate</div>
                      <div className="text-[16px] font-bold text-[var(--color-text)]">
                        {((backtestResult.win_rate || 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Max DD</div>
                      <div className="text-[16px] font-bold text-[var(--color-danger)]">
                        {backtestResult.max_drawdown_pct?.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Trades</div>
                      <div className="text-[16px] font-bold text-[var(--color-text)]">
                        {backtestResult.total_trades}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Config panel */}
        <BlockConfig block={selectedBlock} onUpdate={updateBlockParams} />
      </div>
    </div>
  );
}
