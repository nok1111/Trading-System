import { useState } from "react";
import { ChevronDown, ChevronUp, Clock } from "lucide-react";
import type { SinceLastVisitData } from "../../lib/intelligenceTypes";

const COLOR_MAP: Record<string, string> = {
  green: "text-[var(--color-success)]",
  red: "text-[var(--color-danger)]",
  yellow: "text-[var(--color-warning)]",
  blue: "text-[var(--color-primary)]",
  orange: "text-[#f97316]",
  white: "text-[var(--color-text)]",
  gray: "text-[var(--color-text-muted)]",
  black: "text-[#6b7280]",
};

export function SinceLastVisit({ data, loading }: { data: SinceLastVisitData | null; loading: boolean }) {
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <div className="panel p-5">
        <div className="h-5 w-48 bg-[var(--color-surface-2)] rounded animate-pulse mb-3" />
        <div className="h-4 w-full bg-[var(--color-surface-2)] rounded animate-pulse mb-2" />
        <div className="h-4 w-3/4 bg-[var(--color-surface-2)] rounded animate-pulse" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="panel p-5">
        <h2 className="text-[18px] font-extrabold text-[var(--color-text)] mb-2">Bienvenido.</h2>
        <p className="text-[12px] text-[var(--color-text-muted)]">No hay datos disponibles. El scheduler está recopilando información.</p>
      </div>
    );
  }

  const visibleChanges = expanded ? data.changes : data.changes.slice(0, 5);

  return (
    <div className="panel p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">
          {data.greeting}, Nokturno.
        </h2>
      </div>
      <p className="text-[12px] text-[var(--color-text-muted)] mb-4 flex items-center gap-1.5">
        <Clock size={12} />
        Desde tu última conexión ({data.hoursSinceLogin}h):
      </p>

      <div className="space-y-1.5 mb-4">
        {visibleChanges.map((c) => (
          <div key={c.id} className="flex items-start gap-2.5 py-1">
            <span className="text-[14px] leading-tight mt-0.5">{c.icon}</span>
            <div className="flex-1 min-w-0">
              <span className={`text-[13px] font-bold ${COLOR_MAP[c.color] || "text-[var(--color-text)]"}`}>
                {c.title}
              </span>
              <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{c.detail}</p>
            </div>
          </div>
        ))}
      </div>

      {data.changes.length > 5 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-[11px] font-bold text-[var(--color-primary)] hover:opacity-80 transition-opacity"
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {expanded ? "Mostrar menos" : `Mostrar ${data.changes.length - 5} más`}
        </button>
      )}

      {data.toReview.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
          <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">Qué deberías revisar hoy</p>
          <div className="flex flex-wrap gap-2">
            {data.toReview.map((item, i) => (
              <div key={i} className="flex items-center gap-2 px-3 h-8 rounded-[8px] bg-[var(--color-surface-2)]">
                <span className="text-[12px] font-bold text-[var(--color-text)]">{item.asset}</span>
                <span className="text-[10px] text-[var(--color-text-muted)]">{item.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
