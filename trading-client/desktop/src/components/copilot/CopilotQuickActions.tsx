import { useState } from "react";
import { Scale, Shield, Search, XCircle, Loader2 } from "lucide-react";
import { copilotQuickAction } from "../../lib/copilotApi";

interface QuickAction {
  id: string;
  label: string;
  icon: typeof Scale;
  description: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "rebalance",
    label: "Rebalancear",
    icon: Scale,
    description: "Sugerir rebalanceo del portfolio",
  },
  {
    id: "risk_check",
    label: "Chequeo de Riesgo",
    icon: Shield,
    description: "Evaluación completa de riesgo",
  },
  {
    id: "opportunity_scan",
    label: "Oportunidades",
    icon: Search,
    description: "Escanear mercado para oportunidades",
  },
  {
    id: "close_all_review",
    label: "Revisar Posiciones",
    icon: XCircle,
    description: "Revisar todas las posiciones",
  },
];

interface CopilotQuickActionsProps {
  onResult: (reply: string, actions: any[], conversationId?: number) => void;
}

export function CopilotQuickActions({ onResult }: CopilotQuickActionsProps) {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleAction = async (actionId: string) => {
    if (loadingAction) return;
    setLoadingAction(actionId);
    try {
      const result = await copilotQuickAction(actionId);
      onResult(
        result.reply || "",
        result.actions || [],
        result.conversation_id
      );
    } catch (err: any) {
      onResult(`Error: ${err.message}`, [], undefined);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {QUICK_ACTIONS.map((action) => {
        const Icon = action.icon;
        const isLoading = loadingAction === action.id;
        return (
          <button
            key={action.id}
            onClick={() => handleAction(action.id)}
            disabled={loadingAction !== null}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-[var(--color-surface-2)] hover:bg-[var(--color-primary)]/15 text-[var(--color-text)] hover:text-[var(--color-primary)] transition-colors disabled:opacity-50"
            title={action.description}
          >
            {isLoading ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Icon size={12} />
            )}
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
