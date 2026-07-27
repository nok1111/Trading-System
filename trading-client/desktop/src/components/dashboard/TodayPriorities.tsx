import { Check, X, Clock, AlertTriangle, Shield } from "lucide-react";
import type { TodayPrioritiesData, PriorityAsset } from "../../lib/intelligenceTypes";
import { cn } from "../../lib/utils";

const REC_COLORS: Record<string, string> = {
  "BUY": "text-[var(--color-success)] bg-[var(--color-success)]/10",
  "BUY ON PULLBACK": "text-[var(--color-success)] bg-[var(--color-success)]/10",
  "SELL": "text-[var(--color-danger)] bg-[var(--color-danger)]/10",
  "HOLD": "text-[var(--color-text-muted)] bg-[var(--color-surface-2)]",
  "WAIT": "text-[var(--color-warning)] bg-[var(--color-warning)]/10",
};

const RISK_COLORS: Record<string, string> = {
  low: "text-[var(--color-success)]",
  medium: "text-[var(--color-warning)]",
  high: "text-[var(--color-danger)]",
};

function PriorityCard({ asset }: { asset: PriorityAsset }) {
  const expiresIn = asset.expiresAt
    ? Math.round((new Date(asset.expiresAt).getTime() - Date.now()) / 3600000)
    : null;

  return (
    <div className="panel p-4 hover:border-[var(--color-primary)]/30 transition-colors cursor-pointer">
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="text-[16px] font-extrabold text-[var(--color-text)]">{asset.asset}</span>
          <span className={cn("ml-2 px-2 py-0.5 rounded-[6px] text-[11px] font-bold", REC_COLORS[asset.recommendation] || REC_COLORS["HOLD"])}>
            {asset.recommendation}
          </span>
        </div>
        {expiresIn !== null && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)]">
            <Clock size={11} />
            Expira en {expiresIn}h
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Confianza</p>
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
              <div
                className="h-full rounded-full bg-[var(--color-primary)]"
                style={{ width: `${asset.confidence}%` }}
              />
            </div>
            <span className="text-[12px] font-bold text-[var(--color-text)]">{asset.confidence}%</span>
          </div>
        </div>
        <div>
          <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Riesgo</p>
          <p className={cn("text-[12px] font-bold mt-1 flex items-center gap-1", RISK_COLORS[asset.risk])}>
            <Shield size={11} />
            {asset.risk === "low" ? "Bajo" : asset.risk === "medium" ? "Medio" : "Alto"}
          </p>
        </div>
      </div>

      <p className="text-[11px] text-[var(--color-text-muted)] mb-3">{asset.mainReason}</p>

      <div className="flex gap-1.5 flex-wrap">
        {asset.reasons.map((r, i) => (
          <span
            key={i}
            className={cn(
              "flex items-center gap-1 px-2 h-6 rounded-[6px] text-[10px] font-bold",
              r.confirmed
                ? "text-[var(--color-success)] bg-[var(--color-success)]/10"
                : "text-[var(--color-text-muted)] bg-[var(--color-surface-2)]"
            )}
          >
            {r.confirmed ? <Check size={11} /> : <X size={11} />}
            {r.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function TodayPriorities({ data, loading }: { data: TodayPrioritiesData | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="panel p-5">
        <div className="h-5 w-40 bg-[var(--color-surface-2)] rounded animate-pulse mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 bg-[var(--color-surface-2)] rounded-[10px] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.priorities.length === 0) {
    return (
      <div className="panel p-5">
        <div className="flex items-center gap-2 mb-2">
          <AlertTriangle size={16} className="text-[var(--color-warning)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Qué revisar hoy</h3>
        </div>
        <p className="text-[12px] text-[var(--color-text-muted)]">No hay prioridades disponibles. Abre posiciones para generar recomendaciones.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle size={16} className="text-[var(--color-warning)]" />
        <h3 className="text-[14px] font-bold text-[var(--color-text)]">Qué revisar hoy</h3>
        <span className="text-[11px] text-[var(--color-text-muted)]">— ordenado por prioridad según Consensus Agent</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.priorities.map((p) => (
          <PriorityCard key={p.id} asset={p} />
        ))}
      </div>
    </div>
  );
}
