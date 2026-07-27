import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { AgentInfo } from "../../lib/intelligenceTypes";

interface AgentListProps {
  agents: AgentInfo[];
  className?: string;
}

export function AgentList({ agents, className }: AgentListProps) {
  if (agents.length === 0) {
    return (
      <EmptyState
        title="Sin agentes"
        description="No hay agentes configurados."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {agents.map((a) => {
        const statusColor =
          a.status === "running" ? "bg-[var(--color-success)]" :
          a.status === "error" ? "bg-[var(--color-danger)]" :
          "bg-[var(--color-text-muted)]";
        return (
          <div
            key={a.agentId}
            className="flex items-center gap-3 rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3"
          >
            <span className={cn("w-2 h-2 rounded-full flex-shrink-0", statusColor)} />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-bold text-[var(--color-text)] truncate">{a.agentName}</p>
              <p className="text-[10px] text-[var(--color-text-muted)]">
                {a.role} — {a.interval}
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">{a.status}</p>
              {a.model && (
                <p className="text-[9px] text-[var(--color-text-muted)]">{a.provider}/{a.model}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
