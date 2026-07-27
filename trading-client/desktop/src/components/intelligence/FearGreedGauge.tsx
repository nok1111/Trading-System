import { Gauge } from "../common/Gauge";
import { DataUnavailable } from "../common/DataUnavailable";
import type { FearGreedData } from "../../lib/intelligenceTypes";

interface FearGreedGaugeProps {
  data: FearGreedData | null;
  loading?: boolean;
}

export function FearGreedGauge({ data, loading }: FearGreedGaugeProps) {
  if (loading) {
    return <div className="h-[120px] rounded-[10px] bg-[var(--color-surface-2)] animate-pulse" />;
  }
  if (!data) return <DataUnavailable label="Fear & Greed" />;

  const color =
    data.value >= 75 ? "var(--color-success)" :
    data.value >= 55 ? "var(--color-primary)" :
    data.value >= 45 ? "var(--color-warning)" :
    data.value >= 25 ? "var(--color-warning)" :
    "var(--color-danger)";

  return (
    <div className="flex flex-col items-center">
      <Gauge value={data.value} label={String(data.value)} sublabel={data.classification} color={color} />
      <p className="text-[10px] text-[var(--color-text-muted)] mt-2">
        Anterior: {data.previousValue} ({data.previousClassification})
      </p>
    </div>
  );
}
