import { ChevronDown, ChevronRight, Lock, AlertTriangle } from "lucide-react";
import { cn } from "../../lib/utils";
import { BrokerStatusBadge } from "./BrokerStatusBadge";
import type { SupportedBroker, BrokerAccount } from "../../lib/brokerTypes";
import { isBrokerConnected, isBrokerDegraded, isBrokerLocked, getModulesForBroker } from "../../lib/brokerTypes";

interface BrokerListGroupProps {
  broker: SupportedBroker;
  account: BrokerAccount | null;
  expanded: boolean;
  onToggle: () => void;
  onConnect: () => void;
  selectedModule: string | null;
  onSelectModule: (moduleId: string) => void;
  collapsed?: boolean;
}

export function BrokerListGroup({
  broker,
  account,
  expanded,
  onToggle,
  onConnect,
  selectedModule,
  onSelectModule,
  collapsed = false,
}: BrokerListGroupProps) {
  const status = account?.status || "NOT_CONNECTED";
  const connected = isBrokerConnected(status);
  const degraded = isBrokerDegraded(status);
  const locked = isBrokerLocked(status);

  const modules = connected || degraded ? getModulesForBroker(broker) : [];

  if (locked) {
    return (
      <div
        onClick={onConnect}
        className={cn(
          "w-full flex items-center rounded-[10px] h-10 text-[13px] font-semibold transition-all cursor-pointer",
          collapsed ? "justify-center" : "gap-2.5 px-2.5",
          "text-[var(--color-text-muted)] opacity-50 hover:opacity-80 hover:bg-[var(--color-surface-hover)]"
        )}
        title={collapsed ? `${broker.displayName} — No conectado` : undefined}
      >
        <Lock size={15} className="flex-shrink-0" />
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate">{broker.displayName}</span>
            <span className="text-[10px] font-bold uppercase tracking-wide">No conectado</span>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      <button
        onClick={onToggle}
        title={collapsed ? broker.displayName : undefined}
        className={cn(
          "w-full flex items-center rounded-[10px] h-10 text-[13px] font-semibold transition-all",
          collapsed ? "justify-center" : "gap-1.5 px-2.5",
          "text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        )}
      >
        {collapsed ? (
          <span className="text-[14px] font-extrabold">{broker.displayName[0]}</span>
        ) : (
          <>
            {expanded ? (
              <ChevronDown size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
            ) : (
              <ChevronRight size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
            )}
            <span className="text-[14px] font-extrabold flex-shrink-0">{broker.displayName[0]}</span>
            <span className="flex-1 text-left truncate">{broker.displayName}</span>
            {degraded && (
              <AlertTriangle size={13} className="text-[var(--color-warning)] flex-shrink-0" />
            )}
            <BrokerStatusBadge status={status} />
          </>
        )}
      </button>

      {expanded && !collapsed && (
        <div className="ml-4 space-y-0.5 border-l border-[var(--color-border)] pl-2">
          {modules.map((m) => (
            <button
              key={m.id}
              onClick={() => onSelectModule(m.id)}
              className={cn(
                "w-full flex items-center rounded-[8px] h-8 text-[12px] font-semibold transition-all px-2.5",
                selectedModule === m.id
                  ? "bg-[var(--color-primary)]/12 text-[var(--color-primary)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]",
                m.comingSoon && "opacity-50 cursor-not-allowed"
              )}
              disabled={m.comingSoon}
            >
              <span className="flex-1 text-left">{m.label}</span>
              {m.comingSoon && (
                <span className="text-[9px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Próx.
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
