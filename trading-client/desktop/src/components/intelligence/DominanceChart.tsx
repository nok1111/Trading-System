import { DataUnavailable } from "../common/DataUnavailable";
import type { DominanceData } from "../../lib/intelligenceTypes";

interface DominanceChartProps {
  data: DominanceData | null;
  loading?: boolean;
}

export function DominanceChart({ data, loading }: DominanceChartProps) {
  if (loading) {
    return <div className="h-[80px] rounded-[10px] bg-[var(--color-surface-2)] animate-pulse" />;
  }
  if (!data) return <DataUnavailable label="BTC Dominance" />;

  const segments = [
    { label: "BTC", value: data.btc, color: "var(--color-primary)" },
    { label: "ETH", value: data.eth, color: "var(--color-accent)" },
    { label: "Others", value: data.others, color: "var(--color-text-muted)" },
  ];

  return (
    <div className="space-y-3">
      <div className="flex h-3 rounded-full overflow-hidden">
        {segments.map((s) => (
          <div
            key={s.label}
            style={{ width: `${s.value}%`, backgroundColor: s.color }}
            className="transition-all"
          />
        ))}
      </div>
      <div className="flex items-center gap-4">
        {segments.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
            <span className="text-[11px] font-semibold text-[var(--color-text-muted)]">{s.label}</span>
            <span className="text-[12px] font-bold text-[var(--color-text)]">{s.value.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
