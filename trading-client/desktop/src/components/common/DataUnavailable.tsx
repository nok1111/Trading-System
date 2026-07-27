import { cn } from "../../lib/utils";

interface DataUnavailableProps {
  label?: string;
  className?: string;
}

export function DataUnavailable({
  label = "Dato no disponible",
  className,
}: DataUnavailableProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 h-7 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[11px] font-semibold text-[var(--color-text-muted)]",
        className
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-danger)]" />
      {label}
    </span>
  );
}
