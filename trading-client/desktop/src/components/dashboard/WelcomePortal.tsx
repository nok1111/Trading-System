import { useState } from "react";
import { Sparkles, TrendingUp, TrendingDown, ArrowRight, Newspaper, ChevronDown, ChevronUp, Wallet, Lightbulb, AlertCircle, Coffee } from "lucide-react";
import type { SinceLastVisitData, BuyRecommendation } from "../../lib/intelligenceTypes";
import type { UserProfileData } from "../../lib/intelligenceApi";
import { cn } from "../../lib/utils";
import { CryptoIcon } from "../CryptoIcon";

function fmtMoney(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${v.toFixed(2)}`;
}

function fmtPct(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

function timeAgo(hours: number): string {
  if (hours < 1) return "hace menos de 1 hora";
  if (hours < 24) return `hace ${hours} horas`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "ayer" : `hace ${days} días`;
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 6) return "Buenas noches";
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

function getExperienceLabel(level: string | null | undefined): string {
  if (level === "beginner") return "Tómate un café y revisemos esto juntos";
  if (level === "advanced") return "Ya tienes los datos listos, vamos al grano";
  return "Esto es lo que vi mientras no estabas";
}

export function WelcomePortal({
  data,
  profile,
  loading,
}: {
  data: SinceLastVisitData | null;
  profile: UserProfileData | null;
  loading: boolean;
}) {
  const [showAllChanges, setShowAllChanges] = useState(false);

  if (loading) {
    return (
      <div className="panel p-6">
        <div className="h-6 w-64 bg-[var(--color-surface-2)] rounded animate-pulse mb-3" />
        <div className="h-4 w-full bg-[var(--color-surface-2)] rounded animate-pulse mb-2" />
        <div className="h-4 w-3/4 bg-[var(--color-surface-2)] rounded animate-pulse" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="panel p-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-[var(--color-primary)]/10 flex items-center justify-center shrink-0">
            <Sparkles size={18} className="text-[var(--color-primary)]" />
          </div>
          <div>
            <h2 className="text-[18px] font-extrabold text-[var(--color-text)] mb-1">¡Hola! Soy tu asistente de trading.</h2>
            <p className="text-[13px] text-[var(--color-text-muted)] leading-relaxed">
              Estoy recopilando información del mercado en segundo plano. En unos minutos tendrás noticias, análisis y oportunidades listas para revisar.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const greeting = getGreeting();
  const username = "Nokturno";
  const hasPortfolio = data.portfolio && data.portfolio.positionsCount > 0;
  const hasBuyRecs = data.buyRecommendations && data.buyRecommendations.length > 0;
  const hasMovers = data.movers && data.movers.length > 0;
  const hasNews = data.highImpactNews && data.highImpactNews.length > 0;
  const hasChanges = data.changes.length > 0;
  const visibleChanges = showAllChanges ? data.changes : data.changes.slice(0, 3);


  return (
    <div className="space-y-3">
      {/* Conversational greeting */}
      <div className="panel p-6">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[var(--color-primary)]/20 to-[var(--color-primary)]/5 flex items-center justify-center shrink-0">
            <Coffee size={20} className="text-[var(--color-primary)]" />
          </div>
          <div className="flex-1">
            <h2 className="text-[17px] font-extrabold text-[var(--color-text)] mb-1.5">
              {greeting}, {username} 👋
            </h2>
            <p className="text-[13px] text-[var(--color-text-muted)] leading-relaxed">
              {getExperienceLabel(profile?.experience_level)}.{" "}
              {hasPortfolio ? (
                <>
                  Tu portfolio{" "}
                  <span className={cn("font-bold", data.portfolio!.totalPnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                    {data.portfolio!.totalPnl >= 0 ? "subió" : "bajó"} {fmtMoney(Math.abs(data.portfolio!.totalPnl))}
                  </span>{" "}
                  desde {timeAgo(data.hoursSinceLogin)}.
                </>
              ) : (
                <>Te fuiste {timeAgo(data.hoursSinceLogin)} y estuve vigilando el mercado.</>
              )}
              {hasNews && ` Hay ${data.highImpactNews!.length} ${data.highImpactNews!.length === 1 ? "noticia que no te puedes perder" : "noticias que valen la pena leer"}.`}
              {hasBuyRecs && ` Y sí, encontré ${data.buyRecommendations!.length} ${data.buyRecommendations!.length === 1 ? "oportunidad" : "oportunidades"} que te van a interesar.`}
            </p>

            {/* Inline portfolio stats - subtle, not card-heavy */}
            {hasPortfolio && (
              <div className="flex items-center gap-4 mt-3 text-[12px]">
                <span className="text-[var(--color-text-muted)]">
                  <Wallet size={11} className="inline mr-1" />
                  {data.portfolio!.positionsCount} {data.portfolio!.positionsCount === 1 ? "posición" : "posiciones"}
                </span>
                {data.portfolio!.bestPerformer && (
                  <span className="text-[var(--color-success)] flex items-center gap-0.5">
                    <TrendingUp size={11} />
                    {data.portfolio!.bestPerformer.asset} {fmtPct(data.portfolio!.bestPerformer.pnl_pct)}
                  </span>
                )}
                {data.portfolio!.worstPerformer && data.portfolio!.worstPerformer.asset !== data.portfolio!.bestPerformer?.asset && (
                  <span className="text-[var(--color-danger)] flex items-center gap-0.5">
                    <TrendingDown size={11} />
                    {data.portfolio!.worstPerformer.asset} {fmtPct(data.portfolio!.worstPerformer.pnl_pct)}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Buy recommendations - conversational, partner-like */}
      {hasBuyRecs && (
        <div className="panel p-5">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={16} className="text-[var(--color-success)]" />
            <p className="text-[13px] font-bold text-[var(--color-text)]">
              {data.buyRecommendations!.length === 1
                ? "Esta oportunidad me llamó la atención — mira por qué:"
                : `Encontré ${data.buyRecommendations!.length} oportunidades. Te explico por qué cada una me parece interesante:`}
            </p>
          </div>
          <div className="space-y-2">
            {data.buyRecommendations!.map((rec, i) => (
              <BuySuggestion key={i} rec={rec} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* High impact news - conversational */}
      {hasNews && (
        <div className="panel p-5">
          <div className="flex items-center gap-2 mb-3">
            <Newspaper size={16} className="text-[var(--color-warning)]" />
            <p className="text-[13px] font-bold text-[var(--color-text)]">
              {data.highImpactNews!.length === 1
                ? "Una noticia importante mientras no estabas:"
                : `${data.highImpactNews!.length} noticias que valen la pena leer:`}
            </p>
          </div>
          <div className="space-y-2">
            {data.highImpactNews!.slice(0, 3).map((n) => (
              <a
                key={n.id}
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-2.5 py-1.5 hover:opacity-80 transition-opacity group"
              >
                <span className={cn(
                  "text-[9px] font-bold uppercase px-1.5 h-5 rounded flex items-center shrink-0 mt-0.5",
                  n.impact === "critical" ? "bg-[var(--color-danger)]/15 text-[var(--color-danger)]" : "bg-[var(--color-warning)]/15 text-[var(--color-warning)]"
                )}>
                  {n.impact === "critical" ? "urgente" : "importante"}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold text-[var(--color-text)] group-hover:text-[var(--color-primary)] transition-colors line-clamp-2">
                    {n.title}
                  </p>
                  <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                    {n.source}{n.assets.length > 0 && ` · ${n.assets.join(", ")}`}
                  </p>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Movers - subtle inline chips */}
      {hasMovers && (
        <div className="panel p-4">
          <p className="text-[12px] font-bold text-[var(--color-text-muted)] mb-2.5">
            <TrendingUp size={12} className="inline mr-1" />
            Lo que se está moviendo ahora mismo:
          </p>
          <div className="flex flex-wrap gap-2">
            {data.movers!.map((m, i) => (
              <div key={i} className="flex items-center gap-1.5 px-2.5 h-7 rounded-full bg-[var(--color-surface-2)]">
                <CryptoIcon symbol={m.asset + "USDT"} size={16} />
                <span className="text-[12px] font-bold text-[var(--color-text)]">{m.asset}</span>
                <span className={cn(
                  "text-[10px] font-bold",
                  m.decision === "BUY" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                )}>
                  {m.decision === "BUY" ? "↑ compra" : "↓ venta"}
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">{m.confidence.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Changes - collapsible, subtle */}
      {hasChanges && (
        <div className="panel p-4">
          <p className="text-[12px] font-bold text-[var(--color-text-muted)] mb-2.5">
            <AlertCircle size={12} className="inline mr-1" />
            {hasChanges === true && data.changes.length === 1
              ? "1 cambio desde tu última visita:"
              : `${data.changes.length} cambios desde tu última visita:`}
          </p>
          <div className="space-y-1">
            {visibleChanges.map((c) => (
              <div key={c.id} className="flex items-start gap-2 py-1">
                <span className="text-[13px] leading-tight mt-0.5">{c.icon}</span>
                <div className="flex-1 min-w-0">
                  <span className="text-[12px] font-semibold text-[var(--color-text)]">{c.title}</span>
                  <p className="text-[11px] text-[var(--color-text-muted)]">{c.detail}</p>
                </div>
              </div>
            ))}
          </div>
          {data.changes.length > 3 && (
            <button
              onClick={() => setShowAllChanges(!showAllChanges)}
              className="flex items-center gap-1 text-[11px] font-bold text-[var(--color-primary)] hover:opacity-80 transition-opacity mt-2"
            >
              {showAllChanges ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {showAllChanges ? "Ver menos" : `Ver los ${data.changes.length - 3} restantes`}
            </button>
          )}
        </div>
      )}

      {/* To review - friendly suggestion */}
      {data.toReview.length > 0 && (
        <div className="panel p-4">
          <p className="text-[12px] font-bold text-[var(--color-text-muted)] mb-2.5">
            <Sparkles size={12} className="inline mr-1" />
            Si tienes un minuto, échale un ojo a esto:
          </p>
          <div className="flex flex-wrap gap-2">
            {data.toReview.map((item, i) => (
              <div key={i} className="flex items-center gap-1.5 px-2.5 h-7 rounded-full bg-[var(--color-surface-2)]">
                <CryptoIcon symbol={item.asset + "USDT"} size={16} />
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

function BuySuggestion({ rec, index }: { rec: BuyRecommendation; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const connector = index === 0 ? "Primero" : index === 1 ? "Luego" : index === 2 ? "Y también" : "Además";
  return (
    <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-success)]/30 transition-colors overflow-hidden">
      <div
        className="flex items-center gap-3 p-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <CryptoIcon symbol={rec.asset + "USDT"} size={36} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-[var(--color-text-muted)]">{connector}:</span>
            <span className="text-[14px] font-extrabold text-[var(--color-text)]">{rec.asset}</span>
            {rec.potentialUpside !== null && (
              <span className="text-[11px] font-bold text-[var(--color-success)]">
                +{rec.potentialUpside}% potencial
              </span>
            )}
            <span className="text-[10px] text-[var(--color-text-muted)]">
              {rec.confidence.toFixed(0)}% confianza
            </span>
          </div>
          <p className="text-[12px] text-[var(--color-text)] mt-1 leading-relaxed line-clamp-2">
            {rec.reason || "Señal de compra detectada por análisis técnico."}
          </p>
          {rec.price !== null && (
            <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
              Precio: ${rec.price.toFixed(2)}{rec.targetPrice !== null && ` → objetivo: $${rec.targetPrice.toFixed(2)}`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
          {rec.brokers.map((b) => (
            <button
              key={b}
              onClick={() => {
                window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "trade", asset: rec.asset, broker: b } }));
              }}
              className="flex items-center gap-1 px-2.5 h-7 rounded-[6px] text-[11px] font-bold text-[var(--color-primary)] bg-[var(--color-primary)]/10 hover:bg-[var(--color-primary)]/20 transition-colors"
            >
              Comprar
              <ArrowRight size={11} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
