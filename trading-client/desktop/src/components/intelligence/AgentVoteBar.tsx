import { cn } from "../../lib/utils";
import type { AgentVote } from "../../lib/intelligenceTypes";

interface AgentVoteBarProps {
  vote: AgentVote;
}

export function AgentVoteBar({ vote }: AgentVoteBarProps) {
  const voteColor =
    vote.vote === "BUY" ? "text-[var(--color-success)]" :
    vote.vote === "SELL" ? "text-[var(--color-danger)]" :
    "text-[var(--color-text-muted)]";

  const barColor =
    vote.vote === "BUY" ? "bg-[var(--color-success)]" :
    vote.vote === "SELL" ? "bg-[var(--color-danger)]" :
    "bg-[var(--color-text-muted)]";

  return (
    <div className="flex items-center gap-2.5 h-8">
      <span className="text-[11px] font-semibold text-[var(--color-text)] w-[100px] truncate">
        {vote.agentName}
      </span>
      <div className="flex-1 h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", barColor)}
          style={{ width: `${vote.confidence}%` }}
        />
      </div>
      <span className={cn("text-[11px] font-bold w-10 text-right", voteColor)}>
        {vote.vote}
      </span>
      <span className="text-[10px] text-[var(--color-text-muted)] w-8 text-right">
        {vote.confidence}%
      </span>
    </div>
  );
}
