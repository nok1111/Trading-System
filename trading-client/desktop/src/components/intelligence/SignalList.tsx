import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { IntelligenceSignal } from "../../lib/intelligenceTypes";
import { SignalCard } from "./SignalCard";

interface SignalListProps {
  signals: IntelligenceSignal[];
  onConfirm?: (signal: IntelligenceSignal) => void;
  className?: string;
}

export function SignalList({ signals, onConfirm, className }: SignalListProps) {
  if (signals.length === 0) {
    return (
      <EmptyState
        title="Sin señales activas"
        description="El Consensus no ha generado señales todavía."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {signals.map((s) => (
        <SignalCard key={s.id} signal={s} onConfirm={onConfirm} />
      ))}
    </div>
  );
}
