import { type ReactNode } from "react";
import { cn } from "../../lib/utils";

type Tone = "default" | "success" | "danger" | "warning" | "primary";

const toneColor: Record<Tone, string> = {
  default: "var(--color-text)",
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  primary: "var(--color-primary)",
};

export interface SummaryItem {
  label: string;
  value: string | number;
  tone?: Tone;
  icon?: ReactNode;
}

export function SummaryBar({ items, className }: { items: SummaryItem[]; className?: string }) {
  return (
    <div className={cn("panel-flat flex items-stretch overflow-hidden", className)}>
      {items.map((item, i) => {
        const color = toneColor[item.tone || "default"];
        return (
          <div
            key={i}
            className={cn(
              "flex-1 flex items-center gap-2.5 px-4 py-2.5",
              i > 0 && "border-l border-[var(--color-border)]"
            )}
          >
            {item.icon && (
              <span style={{ color }} className="flex-shrink-0">
                {item.icon}
              </span>
            )}
            <div className="min-w-0">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                {item.label}
              </div>
              <div className="num text-[16px] font-bold leading-tight mt-0.5" style={{ color }}>
                {item.value}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
