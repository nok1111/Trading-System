import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { MacroEvent } from "../../lib/intelligenceTypes";
import { ArrowRight } from "lucide-react";

interface MacroCalendarProps {
  events: MacroEvent[];
  className?: string;
}

export function MacroCalendar({ events, className }: MacroCalendarProps) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="Sin eventos macro"
        description="No hay eventos macroeconómicos próximos."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {events.map((e) => {
        const impactColor =
          e.impact === "high" ? "border-l-[var(--color-danger)]" :
          e.impact === "medium" ? "border-l-[var(--color-warning)]" :
          "border-l-[var(--color-primary)]";
        return (
          <div
            key={e.id}
            className={cn(
              "rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] border-l-3 p-3",
              impactColor
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-bold text-[var(--color-text)]">{e.event}</span>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">{e.country}</span>
            </div>
            <div className="flex items-center gap-4 mt-2 text-[11px]">
              <div>
                <span className="text-[var(--color-text-muted)]">Forecast: </span>
                <span className="font-bold text-[var(--color-text)]">{e.forecast || "--"}</span>
              </div>
              <div>
                <span className="text-[var(--color-text-muted)]">Prev: </span>
                <span className="font-bold text-[var(--color-text)]">{e.previous || "--"}</span>
              </div>
              {e.actual && (
                <div>
                  <span className="text-[var(--color-text-muted)]">Actual: </span>
                  <span className="font-bold text-[var(--color-success)]">{e.actual}</span>
                </div>
              )}
              <button
                onClick={() => {
                  window.dispatchEvent(new CustomEvent("navigate", {
                    detail: {
                      page: "trade",
                      asset: "BTC",
                      signalType: "macro",
                      signalData: { impact: e.impact, title: e.event },
                    },
                  }));
                }}
                className="flex items-center gap-1 px-2 h-6 rounded-[6px] text-[10px] font-bold text-[var(--color-primary)] bg-[var(--color-primary)]/10 hover:bg-[var(--color-primary)]/20 transition-colors ml-auto"
              >
                Trade
                <ArrowRight size={10} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
