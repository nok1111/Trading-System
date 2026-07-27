import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { IntelligenceReport } from "../../lib/intelligenceTypes";
import { fmtDate } from "../../lib/utils";

interface ReportListProps {
  reports: IntelligenceReport[];
  className?: string;
}

export function ReportList({ reports, className }: ReportListProps) {
  if (reports.length === 0) {
    return (
      <EmptyState
        title="Sin reportes"
        description="No hay reportes generados todavía."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {reports.map((r) => (
        <div
          key={r.id}
          className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-[13px] font-bold text-[var(--color-text)]">
              {r.type === "daily" ? "Daily" : r.type === "weekly" ? "Weekly" : "Monthly"} — {r.asset}
            </span>
            <span className="text-[10px] text-[var(--color-text-muted)]">{fmtDate(r.date)}</span>
          </div>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{r.summary}</p>
        </div>
      ))}
    </div>
  );
}
