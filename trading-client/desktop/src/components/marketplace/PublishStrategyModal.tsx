import { useState } from "react";
import { X, Crown, Upload } from "lucide-react";
import { publishStrategy } from "../../lib/marketplaceApi";
import type { StrategyListing } from "../../lib/marketplaceApi";
import { cn } from "../../lib/utils";

interface PublishStrategyModalProps {
  onClose: () => void;
  onPublished?: (strategy: StrategyListing) => void;
}

const STRATEGY_TYPES = [
  { value: "grid", label: "Grid" },
  { value: "dca", label: "DCA" },
  { value: "custom", label: "Custom" },
  { value: "ai_generated", label: "AI Generated" },
];

export function PublishStrategyModal({ onClose, onPublished }: PublishStrategyModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [strategyType, setStrategyType] = useState("custom");
  const [isPublic, setIsPublic] = useState(true);
  const [isPremium, setIsPremium] = useState(false);
  const [priceMonthly, setPriceMonthly] = useState("");
  const [exchange, setExchange] = useState("");
  const [symbols, setSymbols] = useState("");
  const [configText, setConfigText] = useState("{}");
  const [roi90d, setRoi90d] = useState("");
  const [maxDrawdown, setMaxDrawdown] = useState("");
  const [sharpe, setSharpe] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);

    if (!title.trim()) {
      setError("Title is required");
      return;
    }

    // Validate config JSON
    let configBody: Record<string, unknown> = {};
    try {
      configBody = JSON.parse(configText);
    } catch {
      setError("Invalid config JSON");
      return;
    }

    // Parse symbols
    const symbolsList = symbols
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      const result = await publishStrategy({
        title: title.trim(),
        description: description.trim(),
        strategy_type: strategyType,
        config: configBody,
        is_public: isPublic,
        is_premium: isPremium,
        price_monthly: isPremium && priceMonthly ? parseFloat(priceMonthly) : null,
        roi_90d: roi90d ? parseFloat(roi90d) : null,
        max_drawdown: maxDrawdown ? parseFloat(maxDrawdown) : null,
        sharpe: sharpe ? parseFloat(sharpe) : null,
        exchange: exchange.trim() || null,
        symbols: symbolsList.length > 0 ? symbolsList : null,
      });
      onPublished?.(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish strategy");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="panel max-w-xl w-full max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 panel border-b border-[var(--color-surface-2)] p-4 flex items-center justify-between">
          <h2 className="text-[16px] font-bold text-[var(--color-text)]">Publish Strategy</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-[6px] hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {error && (
            <div className="rounded-[6px] bg-red-500/10 border border-red-500/30 p-2.5">
              <p className="text-[12px] text-red-400">{error}</p>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
              Title <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              placeholder="e.g. BTC Grid Master 2024"
              className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] border border-transparent focus:border-[var(--color-primary)] outline-none"
            />
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Describe your strategy, risk profile, and expected performance..."
              className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] border border-transparent focus:border-[var(--color-primary)] outline-none resize-none"
            />
          </div>

          {/* Strategy type + Exchange */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
                Strategy Type
              </label>
              <select
                value={strategyType}
                onChange={(e) => setStrategyType(e.target.value)}
                className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] border border-transparent focus:border-[var(--color-primary)] outline-none"
              >
                {STRATEGY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
                Exchange (optional)
              </label>
              <input
                type="text"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                placeholder="e.g. binance"
                className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] border border-transparent focus:border-[var(--color-primary)] outline-none"
              />
            </div>
          </div>

          {/* Symbols */}
          <div>
            <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
              Symbols (comma-separated, optional)
            </label>
            <input
              type="text"
              value={symbols}
              onChange={(e) => setSymbols(e.target.value)}
              placeholder="e.g. BTC/USDT, ETH/USDT"
              className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] border border-transparent focus:border-[var(--color-primary)] outline-none"
            />
          </div>

          {/* Config JSON */}
          <div>
            <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
              Strategy Config (JSON)
            </label>
            <textarea
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              rows={4}
              placeholder='{"param1": "value1"}'
              className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] font-mono border border-transparent focus:border-[var(--color-primary)] outline-none resize-none"
            />
          </div>

          {/* Backtest metrics */}
          <div className="rounded-[8px] border border-[var(--color-surface-2)] p-3">
            <p className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide mb-2">
              Backtest Metrics (optional — for verification)
            </p>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">ROI 90d (%)</label>
                <input
                  type="number"
                  value={roi90d}
                  onChange={(e) => setRoi90d(e.target.value)}
                  placeholder="0"
                  step="0.1"
                  className="w-full px-2 py-1.5 rounded-[4px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] border border-transparent focus:border-[var(--color-primary)] outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">Max DD (%)</label>
                <input
                  type="number"
                  value={maxDrawdown}
                  onChange={(e) => setMaxDrawdown(e.target.value)}
                  placeholder="0"
                  step="0.1"
                  className="w-full px-2 py-1.5 rounded-[4px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] border border-transparent focus:border-[var(--color-primary)] outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">Sharpe</label>
                <input
                  type="number"
                  value={sharpe}
                  onChange={(e) => setSharpe(e.target.value)}
                  placeholder="0"
                  step="0.01"
                  className="w-full px-2 py-1.5 rounded-[4px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] border border-transparent focus:border-[var(--color-primary)] outline-none"
                />
              </div>
            </div>
          </div>

          {/* Visibility + Premium */}
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isPublic}
                onChange={(e) => setIsPublic(e.target.checked)}
                className="accent-[var(--color-primary)]"
              />
              <span className="text-[12px] text-[var(--color-text)]">Public listing</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isPremium}
                onChange={(e) => setIsPremium(e.target.checked)}
                className="accent-amber-500"
              />
              <span className="text-[12px] text-[var(--color-text)] flex items-center gap-1">
                <Crown size={12} className="text-amber-400" />
                Premium
              </span>
            </label>
          </div>

          {/* Price (if premium) */}
          {isPremium && (
            <div>
              <label className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide block mb-1.5">
                Monthly Price (USD)
              </label>
              <input
                type="number"
                value={priceMonthly}
                onChange={(e) => setPriceMonthly(e.target.value)}
                placeholder="9.99"
                step="0.01"
                min="0"
                className="w-full px-3 py-2 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] border border-transparent focus:border-[var(--color-primary)] outline-none"
              />
            </div>
          )}

          {/* Submit */}
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className={cn(
                "flex-1 px-4 py-2.5 rounded-[8px] text-[13px] font-bold flex items-center justify-center gap-2 disabled:opacity-50",
                "bg-[var(--color-primary)] text-white hover:opacity-90"
              )}
            >
              <Upload size={14} />
              {submitting ? "Publishing..." : "Publish Strategy"}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-[8px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] font-bold hover:bg-[var(--color-surface-3)]"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
