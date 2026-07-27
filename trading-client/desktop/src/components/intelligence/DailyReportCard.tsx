import { FileText } from "lucide-react";
import { cn } from "../../lib/utils";
import { DataUnavailable } from "../common/DataUnavailable";
import type { DailyReport } from "../../lib/intelligenceTypes";
import { fmtDate } from "../../lib/utils";

interface DailyReportCardProps {
  report: DailyReport | null;
  loading?: boolean;
  className?: string;
}

export function DailyReportCard({ report, loading, className }: DailyReportCardProps) {
  if (loading) {
    return <div className="h-32 rounded-[10px] bg-[var(--color-surface-2)] animate-pulse" />;
  }
  if (!report) return <DataUnavailable label="Reporte diario" />;

  return (
    <div className={cn("rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3", className)}>
      <div className="flex items-center gap-2">
        <FileText size={16} className="text-[var(--color-primary)]" />
        <span className="text-[14px] font-bold text-[var(--color-text)]">Reporte Diario</span>
        <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">{fmtDate(report.date)}</span>
      </div>
      <p className="text-[12px] text-[var(--color-text)]">{report.summary}</p>
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(report.sections).map(([key, value]) => (
          <div key={key} className="rounded-[8px] bg-[var(--color-surface-2)] p-2">
            <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">
              {key.replace(/([A-Z])/g, " $1").trim()}
            </p>
            <p className="text-[11px] text-[var(--color-text)] mt-0.5">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
