import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { IntelligenceAlert } from "../../lib/intelligenceTypes";
import { fmtDate } from "../../lib/utils";

interface AlertListProps {
  alerts: IntelligenceAlert[];
  className?: string;
}

export function AlertList({ alerts, className }: AlertListProps) {
  if (alerts.length === 0) {
    return (
      <EmptyState
        title="Sin alertas"
        description="No hay alertas activas en este momento."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {alerts.map((a) => {
        const sevColor =
          a.severity === "high" ? "border-l-[var(--color-danger)]" :
          a.severity === "medium" ? "border-l-[var(--color-warning)]" :
          "border-l-[var(--color-primary)]";
        return (
          <div
            key={a.id}
            className={cn(
              "rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] border-l-3 p-3",
              sevColor
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-bold text-[var(--color-text)]">{a.asset}</span>
              <span className="text-[10px] text-[var(--color-text-muted)]">{fmtDate(a.timestamp)}</span>
            </div>
            <p className="text-[12px] text-[var(--color-text)] mt-1">{a.message}</p>
            {a.details && (
              <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{a.details}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
