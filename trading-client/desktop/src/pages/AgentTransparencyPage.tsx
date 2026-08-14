import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { cn, fmtDateTime } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { VirtualList } from "../components/common/VirtualList";
import { useI18n } from "../i18n/I18nContext";
import { TrendingUp, TrendingDown, Trophy, AlertTriangle, Activity, BarChart3, Brain } from "lucide-react";

interface DecisionTimelineItem {
  id: number;
  timestamp: string;
  symbol: string;
  action: string;
  confidence: number;
  price_at_decision: number;
  current_price: number | null;
  outcome_pct: number | null;
  correct: boolean | null;
  evaluated: boolean;
  regime: string;
  reason: string;
}

interface TransparencyData {
  status: string;
  days: number;
  summary: {
    total_decisions: number;
    total_evaluated: number;
    win_rate: number;
    confidence_avg: number;
    total_pnl: number;
    total_invested: number;
    ai_pnl_pct: number;
    alpha_vs_btc: number;
    alpha_vs_eth: number;
  };
  decision_timeline: DecisionTimelineItem[];
  performance_attribution: {
    by_symbol: Record<string, { total: number; correct: number; win_rate: number; avg_pnl_pct: number }>;
    by_regime: Record<string, { total: number; correct: number; win_rate: number; avg_pnl_pct: number }>;
    by_action: Record<string, { total: number; correct: number; win_rate: number; avg_pnl_pct: number }>;
  };
  comparison: {
    ai_agent: { pnl_pct: number; pnl_usd: number; win_rate: number };
    paper_trading: { pnl_pct: number; pnl_usd: number };
    buy_hold_btc: { pnl_pct: number; pnl_usd: number; price_then: number; price_now: number };
    buy_hold_eth: { pnl_pct: number; pnl_usd: number; price_then: number; price_now: number };
  };
  monthly_evolution: { month: string; win_rate: number; total: number; avg_pnl_pct: number }[];
  best_decision: DecisionTimelineItem | null;
  worst_decision: DecisionTimelineItem | null;
}

export function AgentTransparencyPage() {
  const { t } = useI18n();
  const [data, setData] = useState<TransparencyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [selectedDecision, setSelectedDecision] = useState<DecisionTimelineItem | null>(null);
  const [decisionDetail, setDecisionDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api<TransparencyData>(`/api/ai-agent/transparency?days=${days}`);
      setData(r);
    } catch (e: any) {
      setError(e.message || "Error al cargar datos de transparencia");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadDecisionDetail = async (decision: DecisionTimelineItem) => {
    setSelectedDecision(decision);
    setDecisionDetail(null);
    setDetailLoading(true);
    try {
      const r = await api<any>(`/api/ai-agent/decision/${decision.id}`);
      setDecisionDetail(r);
    } catch (e: any) {
      setDecisionDetail({ status: "error", error: e.message });
    } finally {
      setDetailLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-64 bg-[var(--color-surface-2)] rounded animate-pulse" />
        <div className="h-32 bg-[var(--color-surface-2)] rounded animate-pulse" />
        <div className="h-64 bg-[var(--color-surface-2)] rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card className="p-6 text-center">
          <AlertTriangle size={32} className="mx-auto text-[var(--color-danger)] mb-3" />
          <p className="text-[14px] font-bold text-[var(--color-text)] mb-1">{t("common.error")}</p>
          <p className="text-[12px] text-[var(--color-text-muted)] mb-4">{error}</p>
          <Button onClick={loadData} variant="default">{t("common.retry")}</Button>
        </Card>
      </div>
    );
  }

  if (!data || data.status !== "ok") {
    return (
      <div className="p-6">
        <Card className="p-6 text-center">
          <Brain size={32} className="mx-auto text-[var(--color-text-muted)] mb-3" />
          <p className="text-[14px] font-bold text-[var(--color-text)] mb-1">{t("agent.noData")}</p>
          <p className="text-[12px] text-[var(--color-text-muted)]">{t("agent.noDataDesc")}</p>
        </Card>
      </div>
    );
  }

  const s = data.summary;
  const c = data.comparison;
  const hasData = s.total_decisions > 0;
  const alphaPositive = s.alpha_vs_btc >= 0;

  return (
    <div className="p-6 space-y-4">
      {/* Header with period selector */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-extrabold text-[var(--color-text)]">{t("agent.performance")}</h1>
          <p className="text-[12px] text-[var(--color-text-muted)]">{t("agent.subtitle")}</p>
        </div>
        <div className="flex gap-1.5">
          {[30, 90, 365].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-3 h-8 rounded-[8px] text-[12px] font-bold transition-colors",
                days === d
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              )}
            >
              {d === 365 ? "1Y" : `${d}D`}
            </button>
          ))}
        </div>
      </div>

      {!hasData ? (
        <Card className="p-8 text-center">
          <Activity size={40} className="mx-auto text-[var(--color-text-muted)] mb-4" />
          <p className="text-[14px] font-bold text-[var(--color-text)] mb-2">{t("agent.noData")}</p>
          <p className="text-[12px] text-[var(--color-text-muted)] max-w-md mx-auto">{t("agent.noDataDesc")}</p>
        </Card>
      ) : (
        <>
          {/* Hero: AI Alpha vs Buy & Hold */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <Trophy size={18} className="text-[var(--color-primary)]" />
              <h2 className="text-[15px] font-extrabold text-[var(--color-text)]">{t("agent.alphaVsMarket")}</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {/* AI Agent */}
              <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-primary)]/30 p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Brain size={14} className="text-[var(--color-primary)]" />
                  <span className="text-[10px] font-bold uppercase text-[var(--color-primary)]">AI Agent</span>
                </div>
                <div className={cn(
                  "text-[22px] font-extrabold",
                  c.ai_agent.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                )}>
                  {c.ai_agent.pnl_pct >= 0 ? "+" : ""}{c.ai_agent.pnl_pct}%
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                  ${c.ai_agent.pnl_usd} PnL · {c.ai_agent.win_rate}% WR
                </div>
              </div>

              {/* Buy & Hold BTC */}
              <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">BTC HODL</span>
                </div>
                <div className={cn(
                  "text-[22px] font-extrabold",
                  c.buy_hold_btc.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                )}>
                  {c.buy_hold_btc.pnl_pct >= 0 ? "+" : ""}{c.buy_hold_btc.pnl_pct}%
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                  ${c.buy_hold_btc.pnl_usd} · ${c.buy_hold_btc.price_then} → ${c.buy_hold_btc.price_now}
                </div>
              </div>

              {/* Buy & Hold ETH */}
              <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">ETH HODL</span>
                </div>
                <div className={cn(
                  "text-[22px] font-extrabold",
                  c.buy_hold_eth.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                )}>
                  {c.buy_hold_eth.pnl_pct >= 0 ? "+" : ""}{c.buy_hold_eth.pnl_pct}%
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                  ${c.buy_hold_eth.pnl_usd} · ${c.buy_hold_eth.price_then} → ${c.buy_hold_eth.price_now}
                </div>
              </div>

              {/* Alpha */}
              <div className={cn(
                "rounded-[10px] p-3 border",
                alphaPositive
                  ? "bg-[var(--color-success)]/5 border-[var(--color-success)]/30"
                  : "bg-[var(--color-danger)]/5 border-[var(--color-danger)]/30"
              )}>
                <div className="flex items-center gap-1.5 mb-1">
                  {alphaPositive ? <TrendingUp size={14} className="text-[var(--color-success)]" /> : <TrendingDown size={14} className="text-[var(--color-danger)]" />}
                  <span className={cn(
                    "text-[10px] font-bold uppercase",
                    alphaPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                  )}>Alpha vs BTC</span>
                </div>
                <div className={cn(
                  "text-[22px] font-extrabold",
                  alphaPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                )}>
                  {alphaPositive ? "+" : ""}{s.alpha_vs_btc}%
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                  vs ETH: {s.alpha_vs_eth >= 0 ? "+" : ""}{s.alpha_vs_eth}%
                </div>
              </div>
            </div>
          </Card>

          {/* Summary stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <StatCard label={t("agent.totalDecisions")} value={String(s.total_decisions)} />
            <StatCard label={t("agent.winRate")} value={`${s.win_rate}%`} color={s.win_rate >= 60 ? "success" : s.win_rate >= 40 ? "warning" : "danger"} />
            <StatCard label={t("agent.confidenceAvg")} value={`${(s.confidence_avg * 100).toFixed(0)}%`} />
            <StatCard label={t("agent.totalPnl")} value={`$${s.total_pnl.toFixed(2)}`} color={s.total_pnl >= 0 ? "success" : "danger"} />
            <StatCard label={t("agent.totalInvested")} value={`$${s.total_invested.toFixed(2)}`} />
          </div>

          {/* Best/Worst decisions */}
          {(data.best_decision || data.worst_decision) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.best_decision && (
                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp size={16} className="text-[var(--color-success)]" />
                    <span className="text-[12px] font-bold text-[var(--color-success)]">{t("agent.bestDecision")}</span>
                  </div>
                  <DecisionCard decision={data.best_decision} onClick={() => loadDecisionDetail(data.best_decision!)} />
                </Card>
              )}
              {data.worst_decision && (
                <Card className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingDown size={16} className="text-[var(--color-danger)]" />
                    <span className="text-[12px] font-bold text-[var(--color-danger)]">{t("agent.worstDecision")}</span>
                  </div>
                  <DecisionCard decision={data.worst_decision} onClick={() => loadDecisionDetail(data.worst_decision!)} />
                </Card>
              )}
            </div>
          )}

          {/* Performance Attribution */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 size={18} className="text-[var(--color-accent)]" />
              <h2 className="text-[15px] font-extrabold text-[var(--color-text)]">{t("agent.attribution")}</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <AttributionSection title={t("agent.bySymbol")} data={data.performance_attribution.by_symbol} />
              <AttributionSection title={t("agent.byRegime")} data={data.performance_attribution.by_regime} />
              <AttributionSection title={t("agent.byAction")} data={data.performance_attribution.by_action} />
            </div>
          </Card>

          {/* Monthly Evolution */}
          {data.monthly_evolution.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center gap-2 mb-4">
                <Activity size={18} className="text-[var(--color-accent)]" />
                <h2 className="text-[15px] font-extrabold text-[var(--color-text)]">{t("agent.monthlyEvolution")}</h2>
              </div>
              <div className="flex items-end gap-2 h-32">
                {data.monthly_evolution.map((m) => (
                  <div key={m.month} className="flex-1 flex flex-col items-center justify-end h-full" title={`${m.month}: ${m.win_rate}% WR (${m.total} ops, ${m.avg_pnl_pct}% avg)`}>
                    <span className="text-[9px] font-bold text-[var(--color-text-muted)] mb-1">{m.win_rate}%</span>
                    <div
                      className={cn(
                        "w-full rounded-t",
                        m.win_rate >= 60 ? "bg-[var(--color-success)]" :
                        m.win_rate >= 40 ? "bg-[var(--color-warning)]" : "bg-[var(--color-danger)]"
                      )}
                      style={{ height: `${Math.max(m.win_rate, 5)}%` }}
                    />
                    <span className="text-[9px] text-[var(--color-text-muted)] mt-1">{m.month.split("-")[1]}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Decision Timeline */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <Brain size={18} className="text-[var(--color-accent)]" />
              <h2 className="text-[15px] font-extrabold text-[var(--color-text)]">{t("agent.decisions")} ({data.decision_timeline.length})</h2>
            </div>
            {data.decision_timeline.length === 0 ? (
              <p className="text-[12px] text-[var(--color-text-muted)] text-center py-8">{t("agent.noData")}</p>
            ) : (
              <VirtualList
                items={data.decision_timeline}
                estimateSize={56}
                height={400}
                renderItem={(d) => (
                  <div onClick={() => loadDecisionDetail(d)} className="cursor-pointer">
                    <DecisionCard decision={d} compact />
                  </div>
                )}
              />
            )}
          </Card>

          {/* Decision Detail Modal */}
          {selectedDecision && (
            <div
              className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm"
              onClick={() => setSelectedDecision(null)}
            >
              <div
                className="w-full max-w-[600px] mx-4 rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-2xl max-h-[80vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="px-6 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CryptoIcon symbol={selectedDecision.symbol} size={28} />
                    <div>
                      <h3 className="text-[15px] font-extrabold text-[var(--color-text)]">{selectedDecision.symbol}</h3>
                      <p className="text-[11px] text-[var(--color-text-muted)]">{fmtDateTime(selectedDecision.timestamp)}</p>
                    </div>
                  </div>
                  <button onClick={() => setSelectedDecision(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                    ✕
                  </button>
                </div>
                <div className="px-6 py-4 space-y-3">
                  {detailLoading ? (
                    <p className="text-[12px] text-[var(--color-text-muted)]">{t("common.loading")}</p>
                  ) : decisionDetail?.status === "ok" ? (
                    <>
                      <div className="grid grid-cols-3 gap-2">
                        <DetailItem label={t("agent.action")} value={decisionDetail.decision.action.toUpperCase()} />
                        <DetailItem label={t("agent.confidence")} value={`${(decisionDetail.decision.confidence * 100).toFixed(0)}%`} />
                        <DetailItem label={t("agent.regime")} value={decisionDetail.decision.factors?.regime || "—"} />
                        <DetailItem label={t("agent.priceAtDecision")} value={`$${decisionDetail.decision.price_at_decision}`} />
                        <DetailItem label={t("agent.currentPrice")} value={decisionDetail.decision.current_price ? `$${decisionDetail.decision.current_price}` : "—"} />
                        <DetailItem
                          label={t("agent.outcome")}
                          value={decisionDetail.decision.outcome_pct !== null ? `${decisionDetail.decision.outcome_pct >= 0 ? "+" : ""}${decisionDetail.decision.outcome_pct}%` : "—"}
                          color={decisionDetail.decision.outcome_pct !== null ? (decisionDetail.decision.outcome_pct >= 0 ? "success" : "danger") : undefined}
                        />
                      </div>
                      {decisionDetail.decision.reason && (
                        <div>
                          <p className="text-[11px] font-bold text-[var(--color-text-muted)] mb-1">{t("agent.reason")}</p>
                          <p className="text-[12px] text-[var(--color-text)] bg-[var(--color-surface-2)] rounded-[8px] p-3">{decisionDetail.decision.reason}</p>
                        </div>
                      )}
                      {decisionDetail.context_logs.length > 0 && (
                        <div>
                          <p className="text-[11px] font-bold text-[var(--color-text-muted)] mb-1">{t("agent.contextLogs")} ({decisionDetail.context_logs.length})</p>
                          <div className="space-y-1 max-h-48 overflow-y-auto">
                            {decisionDetail.context_logs.map((log: any, i: number) => (
                              <div key={i} className="text-[10px] font-mono p-1.5 rounded bg-[var(--color-surface-2)]">
                                <span className={cn(
                                  "font-bold",
                                  log.level === "error" ? "text-[var(--color-danger)]" :
                                  log.level === "warning" ? "text-[var(--color-warning)]" : "text-[var(--color-text-muted)]"
                                )}>[{log.level.toUpperCase()}]</span>{" "}
                                <span className="text-[var(--color-text)]">{log.message}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-[12px] text-[var(--color-danger)]">{decisionDetail?.error || "Error"}</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: "success" | "danger" | "warning" }) {
  const colorClass =
    color === "success" ? "text-[var(--color-success)]" :
    color === "danger" ? "text-[var(--color-danger)]" :
    color === "warning" ? "text-[var(--color-warning)]" :
    "text-[var(--color-text)]";
  return (
    <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3">
      <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">{label}</div>
      <div className={cn("text-[18px] font-extrabold", colorClass)}>{value}</div>
    </div>
  );
}

function DecisionCard({ decision, compact, onClick }: { decision: DecisionTimelineItem; compact?: boolean; onClick?: () => void }) {
  const actionColor =
    decision.action === "BUY" ? "text-[var(--color-success)]" :
    decision.action === "SELL" || decision.action === "SHORT" ? "text-[var(--color-danger)]" :
    "text-[var(--color-text-muted)]";

  const outcomeColor = decision.outcome_pct !== null
    ? decision.outcome_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
    : "text-[var(--color-text-muted)]";

  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-[8px] bg-[var(--color-surface-2)] p-2.5 hover:border-[var(--color-primary)]/40 border border-transparent transition-colors",
        !compact && "mb-2"
      )}
    >
      <CryptoIcon symbol={decision.symbol} size={compact ? 24 : 32} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("text-[12px] font-bold", actionColor)}>{decision.action}</span>
          <span className="text-[11px] text-[var(--color-text-muted)]">{(decision.confidence * 100).toFixed(0)}%</span>
          {decision.regime !== "unknown" && (
            <span className="text-[9px] text-[var(--color-text-muted)] bg-[var(--color-surface)] px-1.5 rounded">{decision.regime}</span>
          )}
        </div>
        <p className="text-[10px] text-[var(--color-text-muted)]">{fmtDateTime(decision.timestamp)}</p>
      </div>
      <div className="text-right">
        {decision.outcome_pct !== null ? (
          <span className={cn("text-[13px] font-bold", outcomeColor)}>
            {decision.outcome_pct >= 0 ? "+" : ""}{decision.outcome_pct}%
          </span>
        ) : decision.evaluated ? (
          <span className="text-[11px] text-[var(--color-text-muted)]">—</span>
        ) : (
          <span className="text-[10px] text-[var(--color-text-muted)]">pending</span>
        )}
        {decision.correct !== null && (
          <div className={cn("text-[10px] font-bold", decision.correct ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
            {decision.correct ? "✓" : "✗"}
          </div>
        )}
      </div>
    </div>
  );
}

function AttributionSection({ title, data }: { title: string; data: Record<string, { total: number; correct: number; win_rate: number; avg_pnl_pct: number }> }) {
  const entries = Object.entries(data).sort((a, b) => b[1].avg_pnl_pct - a[1].avg_pnl_pct).slice(0, 8);
  if (entries.length === 0) return null;
  return (
    <div>
      <p className="text-[12px] font-bold text-[var(--color-text)] mb-2">{title}</p>
      <div className="space-y-1.5">
        {entries.map(([key, stats]) => (
          <div key={key} className="flex items-center justify-between text-[11px]">
            <span className="text-[var(--color-text)] font-semibold truncate max-w-[100px]">{key}</span>
            <div className="flex items-center gap-2">
              <span className={cn(
                "font-bold",
                stats.win_rate >= 60 ? "text-[var(--color-success)]" :
                stats.win_rate >= 40 ? "text-[var(--color-warning)]" : "text-[var(--color-danger)]"
              )}>{stats.win_rate}%</span>
              <span className={cn(
                "text-[10px]",
                stats.avg_pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>{stats.avg_pnl_pct >= 0 ? "+" : ""}{stats.avg_pnl_pct}%</span>
              <span className="text-[9px] text-[var(--color-text-muted)]">({stats.total})</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailItem({ label, value, color }: { label: string; value: string; color?: "success" | "danger" }) {
  const colorClass =
    color === "success" ? "text-[var(--color-success)]" :
    color === "danger" ? "text-[var(--color-danger)]" :
    "text-[var(--color-text)]";
  return (
    <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5">
      <div className="text-[9px] text-[var(--color-text-muted)] uppercase mb-0.5">{label}</div>
      <div className={cn("text-[13px] font-bold", colorClass)}>{value}</div>
    </div>
  );
}
