import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { Scenario } from "../../lib/intelligenceTypes";

interface ScenarioTableProps {
  scenarios: Scenario[];
  className?: string;
}

export function ScenarioTable({ scenarios, className }: ScenarioTableProps) {
  if (scenarios.length === 0) {
    return (
      <EmptyState
        title="Sin escenarios"
        description="No hay escenarios generados."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {scenarios.map((s, i) => (
        <div key={i} className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3">
          <p className="text-[13px] font-bold text-[var(--color-text)] mb-2">{s.asset}</p>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-[8px] bg-[var(--color-success)]/8 p-2 text-center">
              <p className="text-[10px] font-bold text-[var(--color-success)] uppercase">Bullish</p>
              <p className="text-[14px] font-extrabold text-[var(--color-text)]">{s.bullish.target}</p>
              <p className="text-[10px] text-[var(--color-text-muted)]">{s.bullish.probability}%</p>
            </div>
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2 text-center">
              <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Base</p>
              <p className="text-[14px] font-extrabold text-[var(--color-text)]">{s.base.target}</p>
              <p className="text-[10px] text-[var(--color-text-muted)]">{s.base.probability}%</p>
            </div>
            <div className="rounded-[8px] bg-[var(--color-danger)]/8 p-2 text-center">
              <p className="text-[10px] font-bold text-[var(--color-danger)] uppercase">Bearish</p>
              <p className="text-[14px] font-extrabold text-[var(--color-text)]">{s.bearish.target}</p>
              <p className="text-[10px] text-[var(--color-text-muted)]">{s.bearish.probability}%</p>
            </div>
          </div>
          {(s.supports.length > 0 || s.resistances.length > 0) && (
            <div className="flex gap-4 mt-2 text-[10px]">
              <div>
                <span className="text-[var(--color-success)] font-bold">Supports: </span>
                <span className="text-[var(--color-text-muted)]">{s.supports.join(", ")}</span>
              </div>
              <div>
                <span className="text-[var(--color-danger)] font-bold">Resistances: </span>
                <span className="text-[var(--color-text-muted)]">{s.resistances.join(", ")}</span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
