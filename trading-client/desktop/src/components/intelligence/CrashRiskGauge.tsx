import { Gauge } from "../common/Gauge";
import { DataUnavailable } from "../common/DataUnavailable";

interface CrashRiskGaugeProps {
  crashRisk: number | null;
  loading?: boolean;
}

export function CrashRiskGauge({ crashRisk, loading }: CrashRiskGaugeProps) {
  if (loading) {
    return <div className="h-[120px] rounded-[10px] bg-[var(--color-surface-2)] animate-pulse" />;
  }
  if (crashRisk == null) return <DataUnavailable label="Crash Risk" />;

  const pct = Math.round(crashRisk * 100);
  const color =
    pct >= 70 ? "var(--color-danger)" :
    pct >= 40 ? "var(--color-warning)" :
    "var(--color-success)";

  return (
    <div className="flex flex-col items-center">
      <Gauge value={pct} label={`${pct}%`} sublabel="Crash Risk" color={color} />
    </div>
  );
}
