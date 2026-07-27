import { CheckCircle2, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "../../lib/utils";
import type { Recommendation } from "../../lib/intelligenceTypes";

interface PortfolioMatchCardProps {
  recommendation: Recommendation | null;
  loading?: boolean;
}

export function PortfolioMatchCard({ recommendation, loading }: PortfolioMatchCardProps) {
  if (loading) {
    return <div className="h-20 rounded-[10px] bg-[var(--color-surface-2)] animate-pulse" />;
  }
  if (!recommendation) return null;

  const isBuy = recommendation.action.toLowerCase().includes("buy");
  const isSell = recommendation.action.toLowerCase().includes("sell");
  const Icon = isBuy ? TrendingUp : isSell ? TrendingDown : CheckCircle2;
  const color = isBuy ? "text-[var(--color-success)]" : isSell ? "text-[var(--color-danger)]" : "text-[var(--color-text-muted)]";

  return (
    <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 space-y-2">
      <div className="flex items-center gap-2">
        <Icon size={16} className={color} />
        <span className={cn("text-[13px] font-bold", color)}>{recommendation.action}</span>
        <span className="text-[12px] font-bold text-[var(--color-text)]">{recommendation.asset}</span>
        <span className="text-[11px] text-[var(--color-text-muted)] ml-auto">
          {recommendation.confidence}% confianza
        </span>
      </div>
      <p className="text-[11px] text-[var(--color-text-muted)]">{recommendation.reason}</p>
      {recommendation.targetAllocation != null && (
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-[var(--color-text-muted)]">Allocación objetivo:</span>
          <span className="font-bold text-[var(--color-text)]">{recommendation.targetAllocation}%</span>
        </div>
      )}
    </div>
  );
}
