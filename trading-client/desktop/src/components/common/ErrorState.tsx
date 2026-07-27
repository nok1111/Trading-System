import { AlertCircle } from "lucide-react";
import { cn } from "../../lib/utils";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ message, onRetry, className }: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center",
        className
      )}
    >
      <AlertCircle
        size={32}
        className="mb-3 text-[var(--color-danger)] opacity-70"
      />
      <p className="text-[14px] font-bold text-[var(--color-text)]">
        Error
      </p>
      <p className="mt-1 text-[12px] text-[var(--color-text-muted)] max-w-[320px]">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 h-9 rounded-[10px] bg-[var(--color-primary)] text-white text-[13px] font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
        >
          Reintentar
        </button>
      )}
    </div>
  );
}
