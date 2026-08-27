import { Download, Star, TrendingUp, TrendingDown, Crown, Lock } from "lucide-react";
import type { StrategyListing } from "../../lib/marketplaceApi";
import { cn } from "../../lib/utils";

interface StrategyCardProps {
  strategy: StrategyListing;
  onClick?: (strategy: StrategyListing) => void;
}

const TYPE_LABELS: Record<string, string> = {
  grid: "Grid",
  dca: "DCA",
  custom: "Custom",
  ai_generated: "AI",
};

const TYPE_COLORS: Record<string, string> = {
  grid: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  dca: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  custom: "bg-gray-500/15 text-gray-400 border-gray-500/30",
  ai_generated: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

export function StrategyCard({ strategy, onClick }: StrategyCardProps) {
  const verification = strategy.verification;
  const roi = verification?.roi_90d;
  const maxDD = verification?.max_drawdown;
  const roiPositive = roi != null && roi >= 0;

  return (
    <div
      onClick={() => onClick?.(strategy)}
      className="panel p-4 card-hover cursor-pointer transition-all hover:border-[var(--color-primary)]/40"
    >
      {/* Header: title + badges */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-[14px] font-bold text-[var(--color-text)] truncate">
            {strategy.title}
          </h3>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5 truncate">
            {strategy.creator_name}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={cn(
              "px-2 py-0.5 rounded-[4px] text-[10px] font-bold border",
              TYPE_COLORS[strategy.strategy_type] || TYPE_COLORS.custom
            )}
          >
            {TYPE_LABELS[strategy.strategy_type] || strategy.strategy_type}
          </span>
          {strategy.is_premium ? (
            <span className="flex items-center gap-0.5 px-2 py-0.5 rounded-[4px] text-[10px] font-bold border bg-amber-500/15 text-amber-400 border-amber-500/30">
              <Crown size={9} />
              PRO
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-bold border bg-green-500/15 text-green-400 border-green-500/30">
              FREE
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-[12px] text-[var(--color-text-muted)] line-clamp-2 mb-3 min-h-[32px]">
        {strategy.description || "No description provided"}
      </p>

      {/* Metrics row */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div className="text-center">
          <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
            ROI 90d
          </p>
          <p
            className={cn(
              "text-[13px] font-bold flex items-center justify-center gap-0.5",
              roi == null
                ? "text-[var(--color-text-muted)]"
                : roiPositive
                  ? "text-[var(--color-success)]"
                  : "text-[var(--color-danger)]"
            )}
          >
            {roi == null ? (
              "--"
            ) : (
              <>
                {roiPositive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                {roiPositive ? "+" : ""}
                {roi.toFixed(1)}%
              </>
            )}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
            Max DD
          </p>
          <p
            className={cn(
              "text-[13px] font-bold",
              maxDD == null
                ? "text-[var(--color-text-muted)]"
                : maxDD > 20
                  ? "text-[var(--color-danger)]"
                  : "text-[var(--color-text)]"
            )}
          >
            {maxDD == null ? "--" : `${maxDD.toFixed(1)}%`}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
            Rating
          </p>
          <p className="text-[13px] font-bold flex items-center justify-center gap-0.5 text-[var(--color-text)]">
            <Star size={11} className="text-amber-400 fill-amber-400" />
            {strategy.rating_avg > 0 ? strategy.rating_avg.toFixed(1) : "--"}
          </p>
        </div>
        <div className="text-center">
          <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
            Downloads
          </p>
          <p className="text-[13px] font-bold flex items-center justify-center gap-0.5 text-[var(--color-text)]">
            <Download size={11} className="text-[var(--color-text-muted)]" />
            {strategy.downloads}
          </p>
        </div>
      </div>

      {/* Footer: exchange + price */}
      <div className="flex items-center justify-between pt-2 border-t border-[var(--color-surface-2)]">
        <span className="text-[10px] text-[var(--color-text-muted)]">
          {strategy.exchange ? strategy.exchange.toUpperCase() : "Any exchange"}
        </span>
        {strategy.is_premium && strategy.price_monthly != null ? (
          <span className="text-[11px] font-bold text-amber-400 flex items-center gap-0.5">
            <Lock size={9} />
            ${strategy.price_monthly.toFixed(2)}/mo
          </span>
        ) : (
          <span className="text-[11px] font-bold text-green-400">Free</span>
        )}
      </div>
    </div>
  );
}
