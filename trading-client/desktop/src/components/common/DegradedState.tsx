import { AlertTriangle } from "lucide-react";
import { cn } from "../../lib/utils";

interface DegradedStateProps {
  message?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

export function DegradedState({
  message = "Conexión degradada",
  description = "Algunos datos pueden no estar disponibles. Intenta sincronizar.",
  onRetry,
  className,
}: DegradedStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-10 px-4 text-center",
        className
      )}
    >
      <AlertTriangle
        size={28}
        className="mb-3 text-[var(--color-warning)] opacity-70"
      />
      <p className="text-[14px] font-bold text-[var(--color-text)]">{message}</p>
      <p className="mt-1 text-[12px] text-[var(--color-text-muted)] max-w-[300px]">
        {description}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 h-9 rounded-[10px] bg-[var(--color-warning)] text-white text-[13px] font-semibold hover:opacity-90 transition-opacity"
        >
          Sincronizar
        </button>
      )}
    </div>
  );
}
