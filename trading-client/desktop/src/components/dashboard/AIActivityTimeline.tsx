import { Activity, Bot } from "lucide-react";
import type { AIActivityData, AIActivityEntry } from "../../lib/intelligenceTypes";
import { cn } from "../../lib/utils";

const AGENT_COLORS: Record<string, string> = {
  "Technical": "text-[var(--color-primary)]",
  "News": "text-[var(--color-warning)]",
  "On-chain": "text-[var(--color-success)]",
  "Contrarian": "text-[var(--color-danger)]",
  "Consensus": "text-[#a855f7]",
  "Macro": "text-[#3b82f6]",
};

const AGENT_ICONS: Record<string, string> = {
  "Technical": "📊",
  "News": "📰",
  "On-chain": "⛓️",
  "Contrarian": "🔄",
  "Consensus": "🤖",
  "Macro": "🏛️",
};

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor(diff / 60000);
  if (hours > 0) return `hace ${hours}h ${mins % 60}m`;
  if (mins > 0) return `hace ${mins}m`;
  return "ahora";
}

function ActivityRow({ entry }: { entry: AIActivityEntry }) {
  return (
    <div className="flex items-start gap-3 py-2.5 relative">
      <div className="flex flex-col items-center">
        <div className="w-8 h-8 rounded-full bg-[var(--color-surface-2)] flex items-center justify-center text-[14px] shrink-0">
          {AGENT_ICONS[entry.agent] || "🤖"}
        </div>
        <div className="w-px h-full bg-[var(--color-border)] absolute top-10 left-4" />
      </div>

      <div className="flex-1 min-w-0 pb-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={cn("text-[11px] font-bold", AGENT_COLORS[entry.agent] || "text-[var(--color-text)]")}>
            {entry.agent}
          </span>
          <span className="text-[10px] text-[var(--color-text-muted)]">{timeAgo(entry.timestamp)}</span>
          {entry.decision && (
            <span className={cn(
              "px-1.5 py-0.5 rounded-[4px] text-[9px] font-bold",
              entry.decision === "BUY" ? "text-[var(--color-success)] bg-[var(--color-success)]/10" :
              entry.decision === "SELL" ? "text-[var(--color-danger)] bg-[var(--color-danger)]/10" :
              "text-[var(--color-text-muted)] bg-[var(--color-surface-2)]"
            )}>
              {entry.decision}
              {entry.confidence ? ` ${entry.confidence}%` : ""}
            </span>
          )}
        </div>
        <p className="text-[12px] font-bold text-[var(--color-text)]">{entry.action}</p>
        <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{entry.detail}</p>
      </div>
    </div>
  );
}

export function AIActivityTimeline({ data, loading }: { data: AIActivityData | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="panel p-5">
        <div className="h-5 w-32 bg-[var(--color-surface-2)] rounded animate-pulse mb-4" />
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-12 bg-[var(--color-surface-2)] rounded animate-pulse mb-2" />
        ))}
      </div>
    );
  }

  if (!data || data.entries.length === 0) {
    return (
      <div className="panel p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Actividad de la IA</h3>
        </div>
        <p className="text-[12px] text-[var(--color-text-muted)]">Todavía no hay actividad. En cuanto los agentes empiecen a analizar, vas a ver aquí qué van haciendo.</p>
      </div>
    );
  }

  return (
    <div className="panel p-5">
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} className="text-[var(--color-primary)]" />
        <h3 className="text-[14px] font-bold text-[var(--color-text)]">Lo que mis agentes han estado haciendo</h3>
        <span className="text-[10px] text-[var(--color-text-muted)]">— en tiempo real</span>
      </div>

      <div className="relative">
        {data.entries.map((entry) => (
          <ActivityRow key={entry.id} entry={entry} />
        ))}
      </div>

      <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-[var(--color-border)]">
        <Bot size={12} className="text-[var(--color-text-muted)]" />
        <span className="text-[10px] text-[var(--color-text-muted)]">
          {data.entries.length} cosas que pasaron mientras no estabas
        </span>
      </div>
    </div>
  );
}
