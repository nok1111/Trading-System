import { Play, Square, Clock } from "lucide-react";
import { cn, fmtTime } from "../../lib/utils";
import { Button } from "../ui/Button";
import { DataUnavailable } from "../common/DataUnavailable";
import type { SchedulerStatus } from "../../lib/intelligenceTypes";

interface SchedulerControlsProps {
  status: SchedulerStatus | null;
  onStart: () => void;
  onStop: () => void;
  loading?: boolean;
}

export function SchedulerControls({ status, onStart, onStop, loading }: SchedulerControlsProps) {
  if (!status) return <DataUnavailable label="Scheduler" />;

  return (
    <div className="flex items-center gap-3 p-3 rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)]">
      <span className={cn(
        "w-2 h-2 rounded-full",
        status.running ? "bg-[var(--color-success)] animate-pulse" : "bg-[var(--color-text-muted)]"
      )} />
      <div className="flex-1">
        <p className="text-[13px] font-bold text-[var(--color-text)]">
          Scheduler {status.running ? "Activo" : "Detenido"}
        </p>
        <p className="text-[10px] text-[var(--color-text-muted)]">
          {status.symbols.length} símbolos — {status.interval}
        </p>
      </div>
      {status.lastRun && (
        <span className="text-[10px] text-[var(--color-text-muted)] flex items-center gap-1">
          <Clock size={11} />
          {fmtTime(status.lastRun)}
        </span>
      )}
      {status.running ? (
        <Button variant="danger" size="sm" onClick={onStop} disabled={loading}>
          <Square size={13} />
          Detener
        </Button>
      ) : (
        <Button variant="success" size="sm" onClick={onStart} disabled={loading}>
          <Play size={13} />
          Iniciar
        </Button>
      )}
    </div>
  );
}
