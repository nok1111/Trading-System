import { useEffect, useState } from "react";
import {
  X,
  Star,
  Download,
  TrendingUp,
  TrendingDown,
  Crown,
  CheckCircle2,
  AlertTriangle,
  Activity,
} from "lucide-react";
import type { StrategyListing, StrategyReview } from "../../lib/marketplaceApi";
import {
  getStrategy,
  subscribeStrategy,
  unsubscribeStrategy,
  getStrategyPerformance,
  type StrategyPerformance,
} from "../../lib/marketplaceApi";
import { ReviewForm } from "./ReviewForm";
import { cn } from "../../lib/utils";
import { fmtTimeAgo } from "../../lib/utils";

interface StrategyDetailProps {
  listingId: number;
  onClose: () => void;
  onSubscribed?: () => void;
}

export function StrategyDetail({ listingId, onClose, onSubscribed }: StrategyDetailProps) {
  const [strategy, setStrategy] = useState<StrategyListing | null>(null);
  const [performance, setPerformance] = useState<StrategyPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showReviewForm, setShowReviewForm] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [s, p] = await Promise.all([
          getStrategy(listingId),
          getStrategyPerformance(listingId).catch(() => null),
        ]);
        if (!alive) return;
        setStrategy(s);
        setPerformance(p);
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : "Failed to load strategy");
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    return () => { alive = false; };
  }, [listingId]);

  const handleSubscribe = async () => {
    setSubscribing(true);
    setError(null);
    try {
      await subscribeStrategy(listingId);
      setSubscribed(true);
      onSubscribed?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to subscribe");
    } finally {
      setSubscribing(false);
    }
  };

  const handleUnsubscribe = async () => {
    setSubscribing(true);
    setError(null);
    try {
      await unsubscribeStrategy(listingId);
      setSubscribed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unsubscribe");
    } finally {
      setSubscribing(false);
    }
  };

  const handleReviewSubmitted = async () => {
    setShowReviewForm(false);
    // Reload strategy to show updated reviews
    try {
      const s = await getStrategy(listingId);
      setStrategy(s);
    } catch {}
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="panel p-8 max-w-2xl w-full mx-4">
          <div className="space-y-3">
            <div className="h-8 w-64 bg-[var(--color-surface-2)] rounded animate-pulse" />
            <div className="h-4 w-full bg-[var(--color-surface-2)] rounded animate-pulse" />
            <div className="h-4 w-3/4 bg-[var(--color-surface-2)] rounded animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !strategy) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="panel p-6 max-w-md w-full mx-4">
          <p className="text-[14px] text-[var(--color-danger)] mb-4">
            {error || "Strategy not found"}
          </p>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-[8px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] font-bold hover:bg-[var(--color-surface-3)]"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const verification = strategy.verification;
  const roi = verification?.roi_90d;
  const maxDD = verification?.max_drawdown;
  const roiPositive = roi != null && roi >= 0;
  const reviews = strategy.reviews || [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="panel max-w-2xl w-full max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 panel border-b border-[var(--color-surface-2)] p-4 flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-[18px] font-bold text-[var(--color-text)] truncate">
                {strategy.title}
              </h2>
              {strategy.is_premium && (
                <span className="flex items-center gap-0.5 px-2 py-0.5 rounded-[4px] text-[10px] font-bold border bg-amber-500/15 text-amber-400 border-amber-500/30">
                  <Crown size={9} />
                  PRO
                </span>
              )}
            </div>
            <p className="text-[12px] text-[var(--color-text-muted)]">
              by {strategy.creator_name} · {strategy.strategy_type} ·{" "}
              {strategy.exchange ? strategy.exchange.toUpperCase() : "Any exchange"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-[6px] hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)] shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Description */}
          <div>
            <h3 className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide mb-1.5">
              Description
            </h3>
            <p className="text-[13px] text-[var(--color-text)] leading-relaxed">
              {strategy.description || "No description provided"}
            </p>
          </div>

          {/* Backtest Verification */}
          {verification && (
            <div className="rounded-[8px] border border-[var(--color-surface-2)] p-3">
              <div className="flex items-center gap-2 mb-3">
                <Activity size={14} className="text-[var(--color-primary)]" />
                <h3 className="text-[12px] font-bold text-[var(--color-text)]">
                  Backtest Verification
                </h3>
                {roi != null && roi > -50 && maxDD != null && maxDD < 30 ? (
                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-green-400">
                    <CheckCircle2 size={11} /> Verified
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-amber-400">
                    <AlertTriangle size={11} /> High Risk
                  </span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
                    ROI 90d
                  </p>
                  <p
                    className={cn(
                      "text-[16px] font-bold flex items-center gap-1",
                      roiPositive
                        ? "text-[var(--color-success)]"
                        : "text-[var(--color-danger)]"
                    )}
                  >
                    {roiPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {roi != null ? `${roiPositive ? "+" : ""}${roi.toFixed(1)}%` : "--"}
                  </p>
                </div>
                <div>
                  <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
                    Max Drawdown
                  </p>
                  <p
                    className={cn(
                      "text-[16px] font-bold",
                      maxDD != null && maxDD > 20
                        ? "text-[var(--color-danger)]"
                        : "text-[var(--color-text)]"
                    )}
                  >
                    {maxDD != null ? `${maxDD.toFixed(1)}%` : "--"}
                  </p>
                </div>
                <div>
                  <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
                    Sharpe
                  </p>
                  <p className="text-[16px] font-bold text-[var(--color-text)]">
                    {verification.sharpe != null ? verification.sharpe.toFixed(2) : "--"}
                  </p>
                </div>
              </div>
              {verification.verified_at && (
                <p className="text-[10px] text-[var(--color-text-muted)] mt-2">
                  Verified {fmtTimeAgo(verification.verified_at)}
                </p>
              )}
            </div>
          )}

          {/* Performance stats */}
          {performance && (
            <div className="grid grid-cols-4 gap-2">
              <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
                <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">
                  Downloads
                </p>
                <p className="text-[14px] font-bold text-[var(--color-text)] flex items-center justify-center gap-1">
                  <Download size={11} />
                  {performance.downloads}
                </p>
              </div>
              <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
                <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">
                  Active Subs
                </p>
                <p className="text-[14px] font-bold text-[var(--color-text)]">
                  {performance.active_subscriptions}
                </p>
              </div>
              <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
                <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">
                  Rating
                </p>
                <p className="text-[14px] font-bold text-[var(--color-text)] flex items-center justify-center gap-1">
                  <Star size={11} className="text-amber-400 fill-amber-400" />
                  {performance.rating_avg > 0 ? performance.rating_avg.toFixed(1) : "--"}
                </p>
              </div>
              <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
                <p className="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">
                  Reviews
                </p>
                <p className="text-[14px] font-bold text-[var(--color-text)]">
                  {performance.review_count}
                </p>
              </div>
            </div>
          )}

          {/* Subscribe button */}
          <div className="flex items-center gap-3">
            {subscribed ? (
              <button
                onClick={handleUnsubscribe}
                disabled={subscribing}
                className="flex-1 px-4 py-2.5 rounded-[8px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] font-bold hover:bg-[var(--color-surface-3)] disabled:opacity-50"
              >
                {subscribing ? "Processing..." : "Unsubscribe"}
              </button>
            ) : (
              <button
                onClick={handleSubscribe}
                disabled={subscribing}
                className={cn(
                  "flex-1 px-4 py-2.5 rounded-[8px] text-[13px] font-bold disabled:opacity-50",
                  strategy.is_premium
                    ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30"
                    : "bg-[var(--color-primary)] text-white hover:opacity-90"
                )}
              >
                {subscribing
                  ? "Processing..."
                  : strategy.is_premium
                    ? `Subscribe — $${strategy.price_monthly?.toFixed(2) || "0"}/mo`
                    : "Subscribe — Free"}
              </button>
            )}
            <button
              onClick={() => setShowReviewForm(!showReviewForm)}
              className="px-4 py-2.5 rounded-[8px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[13px] font-bold hover:bg-[var(--color-surface-3)]"
            >
              Review
            </button>
          </div>

          {/* Review form */}
          {showReviewForm && (
            <ReviewForm
              listingId={listingId}
              onSubmitted={handleReviewSubmitted}
              onCancel={() => setShowReviewForm(false)}
            />
          )}

          {/* Reviews list */}
          {reviews.length > 0 && (
            <div>
              <h3 className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide mb-2">
                Reviews ({reviews.length})
              </h3>
              <div className="space-y-2">
                {reviews.map((review: StrategyReview) => (
                  <div
                    key={review.id}
                    className="rounded-[6px] bg-[var(--color-surface-2)] p-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star
                            key={i}
                            size={11}
                            className={
                              i < review.rating
                                ? "text-amber-400 fill-amber-400"
                                : "text-[var(--color-text-muted)]"
                            }
                          />
                        ))}
                      </div>
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        {review.created_at ? fmtTimeAgo(review.created_at) : ""}
                      </span>
                    </div>
                    {review.comment && (
                      <p className="text-[12px] text-[var(--color-text)] mt-1">
                        {review.comment}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Config (collapsed) */}
          {strategy.config_json && strategy.config_json !== "{}" && (
            <details className="rounded-[6px] border border-[var(--color-surface-2)] p-2">
              <summary className="text-[11px] font-bold text-[var(--color-text-muted)] cursor-pointer">
                Strategy Configuration
              </summary>
              <pre className="text-[10px] text-[var(--color-text-muted)] mt-2 overflow-x-auto whitespace-pre-wrap">
                {(() => {
                  try {
                    return JSON.stringify(JSON.parse(strategy.config_json), null, 2);
                  } catch {
                    return strategy.config_json;
                  }
                })()}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
