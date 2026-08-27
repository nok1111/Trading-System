// TaxMethodSelector — lot-relief method picker (FIFO / LIFO / HIFO / Specific ID).

import { cn } from "../../lib/utils";
import type { TaxMethod } from "../../lib/taxApi";

const METHODS: { value: TaxMethod; label: string; description: string }[] = [
  {
    value: "fifo",
    label: "FIFO",
    description: "First In, First Out — oldest lots sold first",
  },
  {
    value: "lifo",
    label: "LIFO",
    description: "Last In, First Out — newest lots sold first",
  },
  {
    value: "hifo",
    label: "HIFO",
    description: "Highest In, First Out — highest cost lots sold first",
  },
  {
    value: "specific_id",
    label: "Specific ID",
    description: "Manually identify which lots to sell",
  },
];

interface TaxMethodSelectorProps {
  value: TaxMethod;
  onChange: (method: TaxMethod) => void;
  className?: string;
}

export function TaxMethodSelector({
  value,
  onChange,
  className,
}: TaxMethodSelectorProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label className="block text-[12px] font-semibold text-[var(--color-text-muted)]">
        Lot-Relief Method
      </label>
      <div className="grid grid-cols-2 gap-2">
        {METHODS.map((m) => {
          const active = m.value === value;
          return (
            <button
              key={m.value}
              onClick={() => onChange(m.value)}
              className={cn(
                "flex flex-col items-start gap-0.5 px-3 py-2 rounded-lg border transition-all cursor-pointer text-left",
                active
                  ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10"
                  : "border-[var(--color-border)] bg-[var(--color-surface-2)] hover:border-[var(--color-primary)]/40",
              )}
            >
              <span
                className={cn(
                  "text-[13px] font-bold",
                  active
                    ? "text-[var(--color-primary)]"
                    : "text-[var(--color-text)]",
                )}
              >
                {m.label}
              </span>
              <span className="text-[10px] text-[var(--color-text-muted)] leading-tight">
                {m.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
