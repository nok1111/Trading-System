import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center",
        className
      )}
    >
      {icon && (
        <div className="mb-3 text-[var(--color-text-muted)] opacity-50">
          {icon}
        </div>
      )}
      <p className="text-[14px] font-bold text-[var(--color-text)]">{title}</p>
      {description && (
        <p className="mt-1 text-[12px] text-[var(--color-text-muted)] max-w-[320px]">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
