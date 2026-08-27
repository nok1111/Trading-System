// TaxSummaryCard — KPI card for a single tax summary metric.

import { type ReactNode } from "react";
import { Card } from "../ui/Card";
import { cn } from "../../lib/utils";

interface TaxSummaryCardProps {
  label: string;
  value: string;
  icon?: ReactNode;
  tone?: "default" | "success" | "danger" | "warning" | "primary";
  sublabel?: string;
  className?: string;
}

const toneStyles: Record<string, string> = {
  default: "text-[var(--color-text)]",
  success: "text-[var(--color-success)]",
  danger: "text-[var(--color-danger)]",
  warning: "text-[var(--color-warning)]",
  primary: "text-[var(--color-primary)]",
};

const iconBg: Record<string, string> = {
  default: "var(--color-surface-2)",
  success: "color-mix(in srgb, var(--color-success) 14%, transparent)",
  danger: "color-mix(in srgb, var(--color-danger) 14%, transparent)",
  warning: "color-mix(in srgb, var(--color-warning) 14%, transparent)",
  primary: "color-mix(in srgb, var(--color-primary) 14%, transparent)",
};

const iconColor: Record<string, string> = {
  default: "var(--color-text-muted)",
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  primary: "var(--color-primary)",
};

export function TaxSummaryCard({
  label,
  value,
  icon,
  tone = "default",
  sublabel,
  className,
}: TaxSummaryCardProps) {
  return (
    <Card className={cn("flex items-center gap-3 p-4", className)}>
      {icon && (
        <span
          className="flex items-center justify-center w-10 h-10 rounded-lg flex-shrink-0"
          style={{
            background: iconBg[tone],
            color: iconColor[tone],
          }}
        >
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-[11px] uppercase font-semibold tracking-wide text-[var(--color-text-muted)]">
          {label}
        </div>
        <div
          className={cn(
            "num text-[20px] font-bold leading-tight mt-0.5 truncate",
            toneStyles[tone],
          )}
        >
          {value}
        </div>
        {sublabel && (
          <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 truncate">
            {sublabel}
          </div>
        )}
      </div>
    </Card>
  );
}
