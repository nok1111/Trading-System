import { cn } from "../../lib/utils";
import type { AgentVote } from "../../lib/intelligenceTypes";

interface AgentVotesGridProps {
  votes: AgentVote[];
}

export function AgentVotesGrid({ votes }: AgentVotesGridProps) {
  if (!votes.length) return null;

  return (
    <div className="grid grid-cols-3 gap-1.5">
      {votes.map((v) => {
        const color =
          v.vote === "BUY" ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" :
          v.vote === "SELL" ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]" :
          "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]";
        return (
          <div
            key={v.agentId}
            className={cn("rounded-[8px] px-2 py-1.5 text-center", color)}
            title={`${v.agentName}: ${v.vote} (${v.confidence}%)`}
          >
            <p className="text-[9px] font-semibold truncate">{v.agentName}</p>
            <p className="text-[12px] font-bold">{v.vote}</p>
          </div>
        );
      })}
    </div>
  );
}
