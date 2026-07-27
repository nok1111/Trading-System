import { cn } from "../../lib/utils";
import type { BrokerConnectionState } from "../../lib/brokerTypes";

interface BrokerStatusBadgeProps {
  status: BrokerConnectionState;
  className?: string;
}

const STATUS_CONFIG: Record<
  BrokerConnectionState,
  { label: string; color: string; bg: string }
> = {
  CONNECTED_READ_ONLY: {
    label: "READ_ONLY",
    color: "text-[var(--color-success)]",
    bg: "bg-[var(--color-success)]/10",
  },
  CONNECTED_TRADING: {
    label: "TRADING",
    color: "text-[var(--color-success)]",
    bg: "bg-[var(--color-success)]/10",
  },
  DEGRADED: {
    label: "DEGRADADO",
    color: "text-[var(--color-warning)]",
    bg: "bg-[var(--color-warning)]/10",
  },
  DISCONNECTED: {
    label: "Desconectado",
    color: "text-[var(--color-text-muted)]",
    bg: "bg-[var(--color-surface-2)]",
  },
  REVOKED: {
    label: "Revocado",
    color: "text-[var(--color-danger)]",
    bg: "bg-[var(--color-danger)]/10",
  },
  SECURITY_BLOCKED: {
    label: "Bloqueado",
    color: "text-[var(--color-danger)]",
    bg: "bg-[var(--color-danger)]/10",
  },
  NOT_CONNECTED: {
    label: "No conectado",
    color: "text-[var(--color-text-muted)]",
    bg: "bg-[var(--color-surface-2)]",
  },
};

export function BrokerStatusBadge({ status, className }: BrokerStatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.NOT_CONNECTED;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 h-5 rounded-[6px] text-[10px] font-bold uppercase tracking-wide",
        config.color,
        config.bg,
        className
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", config.color.replace("text-", "bg-"))} />
      {config.label}
    </span>
  );
}
