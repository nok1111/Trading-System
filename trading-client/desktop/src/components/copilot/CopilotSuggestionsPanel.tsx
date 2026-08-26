import { useEffect, useState, useCallback } from "react";
import {
  Sparkles,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Shield,
  Target,
  Scale,
} from "lucide-react";
import {
  getCopilotSuggestions,
  type CopilotSuggestion,
} from "../../lib/copilotApi";

const SUGGESTION_ICONS: Record<string, typeof Sparkles> = {
  risk_warning: AlertTriangle,
  opportunity: TrendingUp,
  close_position: TrendingDown,
  adjust_sl_tp: Target,
  rebalance: Scale,
};

const PRIORITY_COLORS: Record<string, string> = {
  high: "var(--color-danger)",
  medium: "var(--color-warning)",
  low: "var(--color-text-muted)",
};

export function CopilotSuggestionsPanel() {
  const [suggestions, setSuggestions] = useState<CopilotSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getCopilotSuggestions();
      setSuggestions(result.suggestions);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 120000); // refresh every 2 min
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && suggestions.length === 0) {
    return (
      <div className="panel p-4 min-h-[80px] flex items-center justify-center">
        <div className="text-[var(--color-text-muted)] text-[12px] flex items-center gap-2">
          <Sparkles size={14} className="animate-pulse" />
          Analizando tu portfolio...
        </div>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[13px] font-bold text-[var(--color-text)]">Copilot</h3>
          <button
            onClick={fetchData}
            className="ml-auto text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1 rounded"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
        <div className="text-[12px] text-[var(--color-text-muted)]">
          Todo se ve bien. No hay sugerencias urgentes.
        </div>
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={16} className="text-[var(--color-primary)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Copilot</h3>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-semibold">
          {suggestions.length}
        </span>
        <button
          onClick={fetchData}
          className="ml-auto text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1 rounded"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="space-y-2">
        {suggestions.slice(0, 5).map((s, i) => {
          const Icon = SUGGESTION_ICONS[s.type] || Shield;
          const color = PRIORITY_COLORS[s.priority] || "var(--color-text-muted)";
          const isExpanded = expanded === `${i}`;

          return (
            <div
              key={i}
              className="rounded-lg border border-[var(--color-border)] overflow-hidden cursor-pointer hover:bg-[var(--color-surface-2)] transition-colors"
              onClick={() => setExpanded(isExpanded ? null : `${i}`)}
            >
              <div className="flex items-start gap-2 p-2.5">
                <Icon size={14} style={{ color }} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-semibold text-[var(--color-text)] truncate">
                    {s.title}
                  </div>
                  {isExpanded && (
                    <div className="text-[11px] text-[var(--color-text-muted)] mt-1">
                      {s.detail}
                    </div>
                  )}
                </div>
                <div
                  className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded flex-shrink-0"
                  style={{ color, backgroundColor: `${color}15` }}
                >
                  {s.priority}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
