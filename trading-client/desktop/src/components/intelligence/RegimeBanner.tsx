import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "../../lib/utils";
import type { MarketOverview } from "../../lib/intelligenceTypes";

interface RegimeBannerProps {
  overview: MarketOverview | null;
  loading?: boolean;
}

export function RegimeBanner({ overview, loading }: RegimeBannerProps) {
  if (loading) {
    return <div className="h-12 rounded-[10px] bg-[var(--color-surface-2)] animate-pulse" />;
  }
  if (!overview) return null;

  const isRiskOn = overview.riskOnOff === "risk_on";
  const Icon = isRiskOn ? TrendingUp : overview.riskOnOff === "risk_off" ? TrendingDown : Minus;

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 h-12 rounded-[10px] border",
        isRiskOn
          ? "bg-[var(--color-success)]/8 border-[var(--color-success)]/20"
          : "bg-[var(--color-danger)]/8 border-[var(--color-danger)]/20"
      )}
    >
      <Icon
        size={18}
        className={isRiskOn ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}
      />
      <div className="flex-1 min-w-0">
        <span className={cn(
          "text-[13px] font-bold",
          isRiskOn ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
        )}>
          {isRiskOn ? "Risk On" : "Risk Off"}
        </span>
        <span className="text-[12px] text-[var(--color-text-muted)] ml-2">
          {overview.regime} — {overview.summary}
        </span>
      </div>
    </div>
  );
}
