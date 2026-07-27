import { Lock } from "lucide-react";
import { cn } from "../../lib/utils";

interface LockedStateProps {
  message?: string;
  description?: string;
  className?: string;
}

export function LockedState({
  message = "Bloqueado",
  description = "Conecta tu broker para acceder a este módulo",
  className,
}: LockedStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-10 px-4 text-center",
        className
      )}
    >
      <Lock size={28} className="mb-3 text-[var(--color-text-muted)] opacity-40" />
      <p className="text-[14px] font-bold text-[var(--color-text-muted)]">
        {message}
      </p>
      <p className="mt-1 text-[12px] text-[var(--color-text-muted)] opacity-70 max-w-[300px]">
        {description}
      </p>
    </div>
  );
}
