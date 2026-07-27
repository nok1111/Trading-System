import type { IntelligenceSignal } from "../../lib/intelligenceTypes";
import { AgentVotesGrid } from "./AgentVotesGrid";
import { Badge } from "../ui/Badge";

interface SignalCardProps {
  signal: IntelligenceSignal;
  onConfirm?: (signal: IntelligenceSignal) => void;
}

export function SignalCard({ signal, onConfirm }: SignalCardProps) {
  const decisionColor =
    signal.decision === "BUY" ? "success" :
    signal.decision === "SELL" ? "danger" :
    "default";

  return (
    <div className="rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-extrabold text-[var(--color-text)]">{signal.asset}</span>
          <Badge variant={decisionColor as any}>{signal.decision}</Badge>
          <Badge variant={signal.riskLevel === "high" ? "danger" : signal.riskLevel === "medium" ? "warning" : "success"}>
            {signal.riskLevel}
          </Badge>
        </div>
        <span className="text-[11px] font-bold text-[var(--color-text)]">
          {signal.confidence}% confianza
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2">
          <p className="text-[var(--color-text-muted)] font-semibold">Entrada</p>
          <p className="text-[var(--color-text)] font-bold">
            {signal.entryZone.min} — {signal.entryZone.max}
          </p>
        </div>
        <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2">
          <p className="text-[var(--color-text-muted)] font-semibold">Targets</p>
          <p className="text-[var(--color-text)] font-bold">
            {signal.targets.map((t) => t.price).join(", ")}
          </p>
        </div>
        <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2">
          <p className="text-[var(--color-text-muted)] font-semibold">Invalidación</p>
          <p className="text-[var(--color-danger)] font-bold">
            {signal.invalidation.value}
          </p>
        </div>
      </div>

      {signal.agentVotes.length > 0 && <AgentVotesGrid votes={signal.agentVotes} />}

      <div className="space-y-1">
        <p className="text-[11px] font-bold text-[var(--color-text-muted)]">Razones principales</p>
        <ul className="text-[11px] text-[var(--color-text)] space-y-0.5 list-disc ml-4">
          {signal.mainReasons.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>

      <div className="space-y-1">
        <p className="text-[11px] font-bold text-[var(--color-text-muted)]">Riesgos</p>
        <ul className="text-[11px] text-[var(--color-danger)] space-y-0.5 list-disc ml-4">
          {signal.mainRisks.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </div>

      {signal.requiresConfirmation && onConfirm && (
        <button
          onClick={() => onConfirm(signal)}
          className="w-full h-9 rounded-[10px] bg-[var(--color-primary)] text-white text-[13px] font-semibold hover:bg-[var(--color-primary-hover)] transition-colors"
        >
          Confirmar señal
        </button>
      )}
    </div>
  );
}
