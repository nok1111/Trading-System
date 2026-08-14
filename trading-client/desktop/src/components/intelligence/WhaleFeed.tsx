import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { WhaleActivity } from "../../lib/intelligenceTypes";
import { fmtDate, fmtVol } from "../../lib/utils";
import { ArrowRight } from "lucide-react";

interface WhaleFeedProps {
  activities: WhaleActivity[];
  className?: string;
}

export function WhaleFeed({ activities, className }: WhaleFeedProps) {
  if (activities.length === 0) {
    return (
      <EmptyState
        title="Sin actividad whale"
        description="No se ha detectado actividad de ballenas recientemente."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {activities.map((w) => {
        const isInflow = w.direction === "inflow";
        return (
          <div
            key={w.id}
            className="flex items-center gap-3 rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3"
          >
            <span
              className={cn(
                "text-[10px] font-bold uppercase px-2 h-5 rounded flex items-center",
                isInflow
                  ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                  : "bg-[var(--color-danger)]/10 text-[var(--color-danger)]"
              )}
            >
              {isInflow ? "Inflow" : "Outflow"}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-bold text-[var(--color-text)]">
                {w.amount.toLocaleString()} {w.asset}
              </p>
              <p className="text-[10px] text-[var(--color-text-muted)]">
                {w.exchange ? `via ${w.exchange}` : "OTC"} — {fmtDate(w.timestamp)}
              </p>
            </div>
            <span className="text-[12px] font-bold text-[var(--color-text)]">
              {fmtVol(w.amountUsd)}
            </span>
            <button
              onClick={() => {
                window.dispatchEvent(new CustomEvent("navigate", {
                  detail: {
                    page: "trade",
                    asset: w.asset,
                    signalType: "whale",
                    signalData: { direction: w.direction, amount_usd: w.amountUsd },
                  },
                }));
              }}
              className="flex items-center gap-1 px-2 h-6 rounded-[6px] text-[10px] font-bold text-[var(--color-primary)] bg-[var(--color-primary)]/10 hover:bg-[var(--color-primary)]/20 transition-colors shrink-0"
              title="Operar desde esta señal"
            >
              Trade
              <ArrowRight size={10} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
