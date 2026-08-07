import { useState } from "react";
import { Zap, TrendingUp, TrendingDown, Waves, Flame, Compass, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";
import { cn } from "../../lib/utils";
import type { UserProfileData } from "../../lib/intelligenceApi";

interface AutoPilotPlan {
  risk_tolerance: string;
  experience_level: string;
  capital_range: string;
  trading_goal: string;
  market_overview: {
    symbol: string;
    regime: string;
    adx: number;
    rsi: number;
    atr_percentile: number;
    recommended_strategies: string[];
    confidence: number;
    description: string;
  }[];
  symbol_plans: {
    symbol: string;
    regime: string;
    recommended_strategy: string | null;
    alternative_strategies: string[];
    regime_confidence: number;
    reason: string;
    regime_data: any;
  }[];
  risk_limits: {
    sl_range: [number, number];
    tp_range: [number, number];
    min_confidence: number;
    max_positions: number;
  };
  total_symbols: number;
  recommended_strategies: string[];
  regime_distribution: Record<string, number>;
  summary: string;
  warnings: string[];
  error?: string;
}

const REGIME_ICONS: Record<string, typeof TrendingUp> = {
  trending_up: TrendingUp,
  trending_down: TrendingDown,
  ranging: Waves,
  volatile: Flame,
  squeeze: Compass,
  reversal: AlertTriangle,
};

const REGIME_COLORS: Record<string, string> = {
  trending_up: "var(--color-success)",
  trending_down: "var(--color-danger)",
  ranging: "var(--color-primary)",
  volatile: "var(--color-warning)",
  squeeze: "var(--color-text-muted)",
  reversal: "var(--color-warning)",
};

const REGIME_LABELS: Record<string, string> = {
  trending_up: "Tendencia Alcista",
  trending_down: "Tendencia Bajista",
  ranging: "Lateral",
  volatile: "Alta Volatilidad",
  squeeze: "Compresion",
  reversal: "Reversal",
};

const RISK_LABELS: Record<string, string> = {
  conservative: "Conservador",
  moderate: "Moderado",
  aggressive: "Agresivo",
};

export function AutoPilotWidget({ profile }: { profile: UserProfileData | null }) {
  const [plan, setPlan] = useState<AutoPilotPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    setPlan(null);
    try {
      const r = await api<AutoPilotPlan>("/api/intelligence/auto-pilot/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          risk_tolerance: profile?.risk_tolerance || "moderate",
          experience_level: profile?.experience_level || "beginner",
          capital_range: profile?.capital_range || "100-1000",
          trading_goal: profile?.trading_goal || "growth",
          interval: "1h",
          max_symbols: profile?.risk_tolerance === "conservative" ? 3 : profile?.risk_tolerance === "aggressive" ? 8 : 5,
        }),
      });
      if (r.error) {
        setError(r.error);
      } else {
        setPlan(r);
      }
    } catch (e: any) {
      setError(e.message || "Error al generar plan");
    }
    setLoading(false);
  };

  return (
    <div className="panel p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-[var(--color-primary)]/10 flex items-center justify-center">
            <Zap size={16} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h3 className="text-[14px] font-extrabold text-[var(--color-text)]">Auto-Pilot</h3>
            <p className="text-[10px] text-[var(--color-text-muted)]">
              {profile ? `Perfil: ${RISK_LABELS[profile.risk_tolerance ?? "moderate"] || "Moderado"}` : "Configura tu perfil primero"}
            </p>
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className={cn(
            "h-8 px-4 rounded-[8px] text-[11px] font-bold transition-all",
            loading
              ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
              : "bg-[var(--color-primary)] text-white hover:opacity-90"
          )}
        >
          {loading ? "Analizando..." : plan ? "Regenerar" : "Generar Plan"}
        </button>
      </div>

      {error && (
        <div className="text-[11px] text-[var(--color-danger)] mb-3">{error}</div>
      )}

      {/* Plan results */}
      {plan && !plan.error && (
        <div className="space-y-3">
          {/* Summary */}
          <div className="rounded-[8px] bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/20 p-3">
            <div className="text-[12px] text-[var(--color-text)] font-bold mb-1">{plan.summary}</div>
            <div className="flex gap-3 mt-2 flex-wrap">
              {plan.recommended_strategies.map(s => (
                <span key={s} className="px-2 py-0.5 rounded-[4px] bg-[var(--color-surface-2)] text-[10px] font-bold text-[var(--color-text)]">
                  {s}
                </span>
              ))}
            </div>
          </div>

          {/* Risk config */}
          <div className="grid grid-cols-4 gap-2">
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">Stop Loss</div>
              <div className="text-[12px] font-bold text-[var(--color-danger)]">
                {plan.risk_limits.sl_range[0]}-{plan.risk_limits.sl_range[1]}%
              </div>
            </div>
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">Take Profit</div>
              <div className="text-[12px] font-bold text-[var(--color-success)]">
                {plan.risk_limits.tp_range[0]}-{plan.risk_limits.tp_range[1]}%
              </div>
            </div>
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">Max Pos</div>
              <div className="text-[12px] font-bold text-[var(--color-text)]">{plan.risk_limits.max_positions}</div>
            </div>
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">Min Conf</div>
              <div className="text-[12px] font-bold text-[var(--color-text)]">{(plan.risk_limits.min_confidence * 100).toFixed(0)}%</div>
            </div>
          </div>

          {/* Regime distribution */}
          <div className="flex gap-2 flex-wrap">
            {Object.entries(plan.regime_distribution).map(([regime, count]) => {
              const Icon = REGIME_ICONS[regime] || Waves;
              const color = REGIME_COLORS[regime] || "var(--color-text-muted)";
              return (
                <div key={regime} className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-surface-2)]">
                  <Icon size={11} style={{ color }} />
                  <span className="text-[10px] font-bold" style={{ color }}>
                    {REGIME_LABELS[regime] || regime}
                  </span>
                  <span className="text-[10px] text-[var(--color-text-muted)]">({count})</span>
                </div>
              );
            })}
          </div>

          {/* Symbol plans */}
          <div className="space-y-1.5">
            {plan.symbol_plans.map((sp) => {
              const Icon = REGIME_ICONS[sp.regime] || Waves;
              const color = REGIME_COLORS[sp.regime] || "var(--color-text-muted)";
              return (
                <div key={sp.symbol} className="flex items-center gap-2 p-2 rounded-[6px] bg-[var(--color-surface-2)]">
                  <Icon size={14} style={{ color }} />
                  <span className="text-[12px] font-bold text-[var(--color-text)] w-20">{sp.symbol}</span>
                  <span className="text-[10px] font-bold" style={{ color }}>
                    {REGIME_LABELS[sp.regime] || sp.regime}
                  </span>
                  <span className="text-[10px] text-[var(--color-text-muted)] flex-1 truncate">{sp.reason}</span>
                  {sp.recommended_strategy ? (
                    <span className="px-2 py-0.5 rounded-[4px] bg-[var(--color-primary)]/20 text-[10px] font-bold text-[var(--color-primary)]">
                      {sp.recommended_strategy}
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-[4px] bg-[var(--color-danger)]/20 text-[10px] font-bold text-[var(--color-danger)]">
                      SKIP
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Warnings */}
          {plan.warnings.length > 0 && (
            <div className="rounded-[6px] bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 p-2">
              {plan.warnings.map((w, i) => (
                <div key={i} className="text-[10px] text-[var(--color-warning)] flex items-center gap-1">
                  <AlertTriangle size={10} /> {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!plan && !loading && !error && (
        <div className="text-[11px] text-[var(--color-text-muted)] py-4 text-center">
          Genera un plan personalizado basado en tu perfil y condiciones del mercado.
          <br />
          El sistema detecta el regimen de cada simbolo y recomienda la mejor estrategia.
        </div>
      )}
    </div>
  );
}
