import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { NewsItem } from "../../lib/intelligenceTypes";
import { fmtDate } from "../../lib/utils";

interface NewsFeedProps {
  news: NewsItem[];
  className?: string;
}

export function NewsFeed({ news, className }: NewsFeedProps) {
  if (news.length === 0) {
    return (
      <EmptyState
        title="Sin noticias"
        description="No hay noticias disponibles en este momento."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {news.map((n) => {
        const sentColor =
          n.sentiment === "positive" ? "text-[var(--color-success)]" :
          n.sentiment === "negative" ? "text-[var(--color-danger)]" :
          "text-[var(--color-text-muted)]";
        const impactBg =
          n.impact === "high" ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]" :
          n.impact === "medium" ? "bg-[var(--color-warning)]/10 text-[var(--color-warning)]" :
          "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]";
        return (
          <a
            key={n.id}
            href={n.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 hover:border-[var(--color-border-strong)] transition-colors"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={cn("text-[9px] font-bold uppercase px-1.5 h-4 rounded flex items-center", impactBg)}>
                {n.impact}
              </span>
              <span className={cn("text-[10px] font-semibold", sentColor)}>{n.sentiment}</span>
              <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">{n.source}</span>
            </div>
            <p className="text-[13px] font-bold text-[var(--color-text)] leading-snug">{n.title}</p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{n.summary}</p>
            <div className="flex items-center gap-1.5 mt-2">
              {n.assets.map((a) => (
                <span key={a} className="text-[10px] font-bold px-1.5 h-4 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] flex items-center">
                  {a}
                </span>
              ))}
              <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">{fmtDate(n.timestamp)}</span>
            </div>
          </a>
        );
      })}
    </div>
  );
}
