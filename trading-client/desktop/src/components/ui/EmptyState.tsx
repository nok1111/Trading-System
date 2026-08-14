import { type ReactNode } from "react";
import { cn } from "../../lib/utils";

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-12 text-center", className)}>
      {icon && (
        <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface-2)] flex items-center justify-center mb-3 text-[var(--color-text-muted)]">
          {icon}
        </div>
      )}
      <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-1">{title}</h3>
      {description && (
        <p className="text-[12px] text-[var(--color-text-muted)] max-w-[280px]">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
