import { useState } from "react";
import {
  Check,
  X,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Target,
  Scale,
  Loader2,
} from "lucide-react";

export interface CopilotAction {
  id: string;
  type: string; // close_position | open_trade | set_stop_loss | set_take_profit | rebalance
  params: Record<string, string>;
  reason: string;
}

interface ConfirmationCardProps {
  action: CopilotAction;
  onConfirm: (action: CopilotAction) => Promise<void>;
  onDismiss: () => void;
}

const ACTION_ICONS: Record<string, typeof Check> = {
  close_position: TrendingDown,
  open_trade: TrendingUp,
  set_stop_loss: Target,
  set_take_profit: Target,
  rebalance: Scale,
};

const ACTION_LABELS: Record<string, string> = {
  close_position: "Cerrar Posición",
  open_trade: "Abrir Trade",
  set_stop_loss: "Configurar Stop-Loss",
  set_take_profit: "Configurar Take-Profit",
  rebalance: "Rebalancear",
};

export function ConfirmationCard({ action, onConfirm, onDismiss }: ConfirmationCardProps) {
  const [status, setStatus] = useState<"pending" | "confirming" | "confirmed" | "error">("pending");
  const [error, setError] = useState<string | null>(null);

  const Icon = ACTION_ICONS[action.type] || AlertTriangle;
  const label = ACTION_LABELS[action.type] || action.type;

  const handleConfirm = async () => {
    setStatus("confirming");
    setError(null);
    try {
      await onConfirm(action);
      setStatus("confirmed");
      // Auto-dismiss after 2s
      setTimeout(() => onDismiss(), 2000);
    } catch (err: any) {
      setError(err.message || "Error al ejecutar");
      setStatus("error");
    }
  };

  if (status === "confirmed") {
    return (
      <div className="rounded-lg border border-[var(--color-success)]/30 bg-[var(--color-success)]/10 p-3 flex items-center gap-2">
        <Check size={16} className="text-[var(--color-success)]" />
        <span className="text-[12px] font-semibold text-[var(--color-success)]">
          {label} ejecutado correctamente
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-[var(--color-primary)]/15 flex items-center justify-center">
          <Icon size={14} className="text-[var(--color-primary)]" />
        </div>
        <div className="flex-1">
          <div className="text-[12px] font-bold text-[var(--color-text)]">{label}</div>
          <div className="text-[10px] text-[var(--color-text-muted)]">Acción propuesta por IA</div>
        </div>
      </div>

      {/* Action details */}
      <div className="space-y-1 text-[11px]">
        {Object.entries(action.params).map(([key, value]) => (
          <div key={key} className="flex justify-between">
            <span className="text-[var(--color-text-muted)]">{key}:</span>
            <span className="font-mono text-[var(--color-text)]">{value}</span>
          </div>
        ))}
      </div>

      {/* Reason */}
      {action.reason && (
        <div className="text-[11px] text-[var(--color-text-muted)] italic border-l-2 border-[var(--color-border)] pl-2">
          {action.reason}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-[11px] text-[var(--color-danger)] bg-[var(--color-danger)]/10 rounded px-2 py-1">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={handleConfirm}
          disabled={status === "confirming"}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-bold bg-[var(--color-success)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {status === "confirming" ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Check size={12} />
          )}
          Confirmar
        </button>
        <button
          onClick={onDismiss}
          disabled={status === "confirming"}
          className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-bold bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors disabled:opacity-50"
        >
          <X size={12} />
          Descartar
        </button>
      </div>
    </div>
  );
}
