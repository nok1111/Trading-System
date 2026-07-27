import { PlugZap } from "lucide-react";
import { cn } from "../../lib/utils";

interface NotConnectedStateProps {
  brokerName?: string;
  onConnect?: () => void;
  className?: string;
}

export function NotConnectedState({
  brokerName,
  onConnect,
  className,
}: NotConnectedStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-10 px-4 text-center",
        className
      )}
    >
      <PlugZap
        size={28}
        className="mb-3 text-[var(--color-text-muted)] opacity-40"
      />
      <p className="text-[14px] font-bold text-[var(--color-text-muted)]">
        {brokerName ? `${brokerName} no conectado` : "Broker no conectado"}
      </p>
      <p className="mt-1 text-[12px] text-[var(--color-text-muted)] opacity-70 max-w-[300px]">
        Importa tu API Key para ver tus datos de trading
      </p>
      {onConnect && (
        <button
          onClick={onConnect}
          className="mt-4 px-4 h-9 rounded-[10px] bg-[var(--color-primary)] text-white text-[13px] font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
        >
          Conectar broker
        </button>
      )}
    </div>
  );
}
