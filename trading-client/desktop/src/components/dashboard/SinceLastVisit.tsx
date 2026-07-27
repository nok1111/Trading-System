import { useState } from "react";
import { ChevronDown, ChevronUp, Clock, TrendingUp, TrendingDown, Wallet, ArrowRight, Newspaper } from "lucide-react";
import type { SinceLastVisitData, BuyRecommendation } from "../../lib/intelligenceTypes";
import { cn } from "../../lib/utils";

const COLOR_MAP: Record<string, string> = {
  green: "text-[var(--color-success)]",
  red: "text-[var(--color-danger)]",
  yellow: "text-[var(--color-warning)]",
  blue: "text-[var(--color-primary)]",
  orange: "text-[#f97316]",
  white: "text-[var(--color-text)]",
  gray: "text-[var(--color-text-muted)]",
  black: "text-[#6b7280]",
};

function fmtMoney(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${v.toFixed(2)}`;
}

function fmtPct(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

function PortfolioSummaryCard({ portfolio }: { portfolio: NonNullable<SinceLastVisitData["portfolio"]> }) {
  const pnlPositive = portfolio.totalPnl >= 0;
  return (
    <div className="flex items-center gap-4 flex-wrap">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-[var(--color-surface-2)] flex items-center justify-center">
          <Wallet size={14} className="text-[var(--color-primary)]" />
        </div>
        <div>
          <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">PnL Total</p>
          <p className={cn("text-[16px] font-extrabold", pnlPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
            {fmtMoney(portfolio.totalPnl)}
          </p>
        </div>
      </div>
      <div className="h-8 w-px bg-[var(--color-border)]" />
      <div>
        <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Posiciones</p>
        <p className="text-[14px] font-bold text-[var(--color-text)]">{portfolio.positionsCount}</p>
      </div>
      {portfolio.totalValue > 0 && (
        <>
          <div className="h-8 w-px bg-[var(--color-border)]" />
          <div>
            <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Valor</p>
            <p className="text-[14px] font-bold text-[var(--color-text)]">${portfolio.totalValue.toFixed(0)}</p>
          </div>
        </>
      )}
      {portfolio.bestPerformer && (
        <>
          <div className="h-8 w-px bg-[var(--color-border)]" />
          <div>
            <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase flex items-center gap-1">
              <TrendingUp size={10} className="text-[var(--color-success)]" /> Mejor
            </p>
            <p className="text-[13px] font-bold text-[var(--color-success)]">
              {portfolio.bestPerformer.asset} {fmtPct(portfolio.bestPerformer.pnl_pct)}
            </p>
          </div>
        </>
      )}
      {portfolio.worstPerformer && portfolio.worstPerformer.asset !== portfolio.bestPerformer?.asset && (
        <>
          <div className="h-8 w-px bg-[var(--color-border)]" />
          <div>
            <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase flex items-center gap-1">
              <TrendingDown size={10} className="text-[var(--color-danger)]" /> Peor
            </p>
            <p className="text-[13px] font-bold text-[var(--color-danger)]">
              {portfolio.worstPerformer.asset} {fmtPct(portfolio.worstPerformer.pnl_pct)}
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function BuyRecCard({ rec }: { rec: BuyRecommendation }) {
  return (
    <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-success)]/20 p-3 hover:border-[var(--color-success)]/40 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-extrabold text-[var(--color-text)]">{rec.asset}</span>
          <span className="px-2 py-0.5 rounded-[6px] text-[10px] font-bold text-[var(--color-success)] bg-[var(--color-success)]/10">
            BUY
          </span>
        </div>
        {rec.potentialUpside !== null && (
          <span className="text-[12px] font-bold text-[var(--color-success)] flex items-center gap-0.5">
            <TrendingUp size={12} />
            {rec.potentialUpside}%
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 mb-2">
        {rec.price !== null && (
          <div>
            <p className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">Precio</p>
            <p className="text-[12px] font-bold text-[var(--color-text)]">${rec.price.toFixed(2)}</p>
          </div>
        )}
        {rec.targetPrice !== null && (
          <div>
            <p className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">Target</p>
            <p className="text-[12px] font-bold text-[var(--color-success)]">${rec.targetPrice.toFixed(2)}</p>
          </div>
        )}
        <div>
          <p className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">Confianza</p>
          <p className="text-[12px] font-bold text-[var(--color-text)]">{rec.confidence.toFixed(0)}%</p>
        </div>
      </div>
      {rec.reason && (
        <p className="text-[11px] text-[var(--color-text-muted)] mb-2 line-clamp-1">{rec.reason}</p>
      )}
      <div className="flex items-center gap-1.5 flex-wrap">
        {rec.brokers.map((b) => (
          <button
            key={b}
            onClick={() => {
              window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "trade", asset: rec.asset, broker: b } }));
            }}
            className="flex items-center gap-1 px-2.5 h-7 rounded-[6px] text-[11px] font-bold text-[var(--color-primary)] bg-[var(--color-primary)]/10 hover:bg-[var(--color-primary)]/20 transition-colors"
          >
            Comprar en {b}
            <ArrowRight size={11} />
          </button>
        ))}
      </div>
    </div>
  );
}

function MoverChip({ mover }: { mover: NonNullable<SinceLastVisitData["movers"]>[0] }) {
  const isBuy = mover.decision === "BUY";
  return (
    <div className="flex items-center gap-2 px-3 h-8 rounded-[8px] bg-[var(--color-surface-2)]">
      <span className="text-[12px] font-bold text-[var(--color-text)]">{mover.asset}</span>
      <span className={cn(
        "text-[10px] font-bold px-1.5 py-0.5 rounded",
        isBuy ? "text-[var(--color-success)] bg-[var(--color-success)]/10" : "text-[var(--color-danger)] bg-[var(--color-danger)]/10"
      )}>
        {mover.decision}
      </span>
      <span className="text-[10px] text-[var(--color-text-muted)]">{mover.confidence.toFixed(0)}%</span>
    </div>
  );
}

export function SinceLastVisit({ data, loading }: { data: SinceLastVisitData | null; loading: boolean }) {
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <div className="panel p-5">
        <div className="h-5 w-48 bg-[var(--color-surface-2)] rounded animate-pulse mb-3" />
        <div className="h-4 w-full bg-[var(--color-surface-2)] rounded animate-pulse mb-2" />
        <div className="h-4 w-3/4 bg-[var(--color-surface-2)] rounded animate-pulse" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="panel p-5">
        <h2 className="text-[18px] font-extrabold text-[var(--color-text)] mb-2">Bienvenido.</h2>
        <p className="text-[12px] text-[var(--color-text-muted)]">No hay datos disponibles. El scheduler está recopilando información.</p>
      </div>
    );
  }

  const visibleChanges = expanded ? data.changes : data.changes.slice(0, 5);
  const hasPortfolio = data.portfolio && data.portfolio.positionsCount > 0;
  const hasBuyRecs = data.buyRecommendations && data.buyRecommendations.length > 0;
  const hasMovers = data.movers && data.movers.length > 0;
  const hasNews = data.highImpactNews && data.highImpactNews.length > 0;

  return (
    <div className="panel p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">
          {data.greeting}, Nokturno.
        </h2>
      </div>
      <p className="text-[12px] text-[var(--color-text-muted)] mb-4 flex items-center gap-1.5">
        <Clock size={12} />
        Desde tu última conexión ({data.hoursSinceLogin}h):
      </p>

      {/* Portfolio Summary */}
      {hasPortfolio && (
        <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 mb-4">
          <PortfolioSummaryCard portfolio={data.portfolio!} />
        </div>
      )}

      {/* Buy Recommendations */}
      {hasBuyRecs && (
        <div className="mb-4">
          <p className="text-[11px] font-bold text-[var(--color-success)] uppercase mb-2 flex items-center gap-1.5">
            <TrendingUp size={12} />
            Oportunidades de compra detectadas
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {data.buyRecommendations!.map((rec, i) => (
              <BuyRecCard key={i} rec={rec} />
            ))}
          </div>
        </div>
      )}

      {/* Top Movers */}
      {hasMovers && (
        <div className="mb-4">
          <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">Movimientos destacados</p>
          <div className="flex flex-wrap gap-2">
            {data.movers!.map((m, i) => (
              <MoverChip key={i} mover={m} />
            ))}
          </div>
        </div>
      )}

      {/* High Impact News */}
      {hasNews && (
        <div className="mb-4">
          <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1.5">
            <Newspaper size={12} />
            Noticias de alto impacto
          </p>
          <div className="space-y-1.5">
            {data.highImpactNews!.slice(0, 3).map((n) => (
              <a
                key={n.id}
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-2 py-1 hover:opacity-80 transition-opacity"
              >
                <span className={cn(
                  "text-[9px] font-bold uppercase px-1.5 h-4 rounded flex items-center shrink-0",
                  n.impact === "critical" ? "bg-[var(--color-danger)]/15 text-[var(--color-danger)]" : "bg-[var(--color-warning)]/15 text-[var(--color-warning)]"
                )}>
                  {n.impact}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-bold text-[var(--color-text)] line-clamp-1">{n.title}</p>
                  <p className="text-[10px] text-[var(--color-text-muted)]">{n.source} · {n.assets.join(", ")}</p>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Changes timeline */}
      {data.changes.length > 0 && (
        <div className="mb-2">
          <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">Cambios desde tu última visita</p>
          <div className="space-y-1.5">
            {visibleChanges.map((c) => (
              <div key={c.id} className="flex items-start gap-2.5 py-1">
                <span className="text-[14px] leading-tight mt-0.5">{c.icon}</span>
                <div className="flex-1 min-w-0">
                  <span className={`text-[13px] font-bold ${COLOR_MAP[c.color] || "text-[var(--color-text)]"}`}>
                    {c.title}
                  </span>
                  <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{c.detail}</p>
                </div>
              </div>
            ))}
          </div>
          {data.changes.length > 5 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-[11px] font-bold text-[var(--color-primary)] hover:opacity-80 transition-opacity mt-2"
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {expanded ? "Mostrar menos" : `Mostrar ${data.changes.length - 5} más`}
            </button>
          )}
        </div>
      )}

      {/* To review */}
      {data.toReview.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
          <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">Qué deberías revisar hoy</p>
          <div className="flex flex-wrap gap-2">
            {data.toReview.map((item, i) => (
              <div key={i} className="flex items-center gap-2 px-3 h-8 rounded-[8px] bg-[var(--color-surface-2)]">
                <span className="text-[12px] font-bold text-[var(--color-text)]">{item.asset}</span>
                <span className="text-[10px] text-[var(--color-text-muted)]">{item.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
