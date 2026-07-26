import { type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type BadgeVariant = "default" | "success" | "danger" | "warning" | "primary" | "accent";

const badgeStyles: Record<BadgeVariant, string> = {
  default:
    "bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]",
  success: "bg-[var(--color-success)]/15 text-[var(--color-success)]",
  danger: "bg-[var(--color-danger)]/15 text-[var(--color-danger)]",
  warning: "bg-[var(--color-warning)]/15 text-[var(--color-warning)]",
  primary: "bg-[var(--color-primary)]/15 text-[var(--color-primary)]",
  accent: "bg-[var(--color-accent)]/15 text-[var(--color-accent)]",
};

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
} & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-[3px] rounded-md text-[11px] font-bold uppercase tracking-wide whitespace-nowrap",
        badgeStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
