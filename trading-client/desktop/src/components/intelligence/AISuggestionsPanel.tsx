import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus, ArrowRight, Sparkles, Clock, Shield } from "lucide-react";
import { api } from "../../lib/api";
import { useBrokerContext } from "../../context/BrokerContext";
import { isBrokerConnected } from "../../lib/brokerTypes";
import { cn, fmt, fmtDate } from "../../lib/utils";
import { LoadingSkeleton } from "../common/LoadingSkeleton";
import { CryptoIcon } from "../CryptoIcon";

interface Signal {
  id: number;
  timestamp: string;
  symbol: string;
  signal_type: string;
  confidence: string;
  entry_price: string | null;
  suggested_stop_loss: string | null;
  suggested_take_profit: string | null;
  strategy_name: string;
  explanation: string;
  status: string;
}

interface UserProfile {
  user_id: number;
  experience_level: string;
  risk_tolerance: string;
  asset_interests: string[];
  capital_range: string;
  preferred_strategies: string[];
  trading_goal: string;
  preferred_language: string;
  onboarding_completed: boolean;
}

type TimeHorizon = "scalp" | "short_term" | "swing" | "long_term";
type Rating = "A+" | "A" | "B+" | "B" | "C+" | "C" | "D";

interface EnrichedSignal extends Signal {
  rating: Rating;
  ratingScore: number;
  timeHorizon: TimeHorizon;
  timeHorizonLabel: string;
  aiComment: string;
  riskMatch: boolean;
  potentialReturn: number | null;
}

const RATING_COLORS: Record<Rating, string> = {
  "A+": "text-[var(--color-success)]",
  "A": "text-[var(--color-success)]",
  "B+": "text-[var(--color-primary)]",
  "B": "text-[var(--color-primary)]",
  "C+": "text-[var(--color-warning)]",
  "C": "text-[var(--color-warning)]",
  "D": "text-[var(--color-danger)]",
};

const HORIZON_LABELS: Record<TimeHorizon, string> = {
  scalp: "Scalp (min-horas)",
  short_term: "Corto plazo (1-3 días)",
  swing: "Swing (1-2 semanas)",
  long_term: "Largo plazo (meses)",
};

const HORIZON_ICONS: Record<TimeHorizon, string> = {
  scalp: "⚡",
  short_term: "📅",
  swing: "📊",
  long_term: "🎯",
};

function computeRating(confidence: number): { rating: Rating; score: number } {
  const score = confidence * 100;
  if (score >= 90) return { rating: "A+", score };
  if (score >= 80) return { rating: "A", score };
  if (score >= 70) return { rating: "B+", score };
  if (score >= 60) return { rating: "B", score };
  if (score >= 50) return { rating: "C+", score };
  if (score >= 40) return { rating: "C", score };
  return { rating: "D", score };
}

function inferTimeHorizon(signal: Signal, profile: UserProfile | null): TimeHorizon {
  const strat = (signal.strategy_name || "").toLowerCase();
  const explanation = (signal.explanation || "").toLowerCase();

  if (strat.includes("scalp") || explanation.includes("scalp")) return "scalp";
  if (strat.includes("swing") || explanation.includes("swing")) return "swing";
  if (strat.includes("long") || explanation.includes("largo plazo") || explanation.includes("long term")) return "long_term";

  if (profile) {
    if (profile.risk_tolerance === "conservative") return "swing";
    if (profile.risk_tolerance === "aggressive") return "short_term";
  }
  return "short_term";
}

function generateAiComment(signal: Signal, profile: UserProfile | null, horizon: TimeHorizon): string {
  const parts: string[] = [];
  const conf = parseFloat(signal.confidence);
  const decision = signal.signal_type;

  const profileLabel = profile
    ? { conservative: "conservador", moderate: "moderado", aggressive: "agresivo" }[profile.risk_tolerance] || profile.risk_tolerance
    : null;

  if (decision === "BUY") {
    parts.push("Oportunidad de compra detectada");
  } else if (decision === "SELL") {
    parts.push("Señal de venta identificada");
  } else {
    parts.push("Mantener posición recomendado");
  }

  if (conf >= 0.8) parts.push("con alta convicción");
  else if (conf >= 0.6) parts.push("con convicción moderada");
  else parts.push("con convicción baja");

  const expl = signal.explanation || "";
  const cleanExpl = expl.replace(/^\[AI Agent\]\s*/i, "");

  if (profile && profileLabel) {
    // Risk tolerance references
    if (profile.risk_tolerance === "conservative" && conf < 0.7) {
      parts.push(`⚠️ Tu perfil ${profileLabel} requiere mayor convicción — esta señal queda por debajo del umbral`);
    } else if (profile.risk_tolerance === "conservative" && conf >= 0.7) {
      parts.push(`✅ Convicción suficiente para tu perfil ${profileLabel}`);
    } else if (profile.risk_tolerance === "aggressive" && conf >= 0.8) {
      parts.push(`✅ Alineado con tu perfil ${profileLabel} — oportunidad de alto potencial`);
    } else if (profile.risk_tolerance === "moderate" && conf >= 0.6) {
      parts.push(`✅ Adecuado para tu perfil ${profileLabel}`);
    }

    // Strategy references
    if (profile.preferred_strategies.includes("dca") && horizon === "long_term") {
      parts.push("💡 Ideal para tu estrategia DCA");
    }
    if (profile.preferred_strategies.includes("swing") && horizon === "swing") {
      parts.push("🌊 Encaja con tu estrategia de swing trading");
    }
    if (profile.preferred_strategies.includes("scalping") && horizon === "scalp") {
      parts.push("🎯 Apropiado para tu estilo de scalping");
    }

    // Goal references
    if (profile.trading_goal === "preservation" && decision === "BUY" && conf < 0.8) {
      parts.push("🛡️ Tu objetivo es preservación — considera esperar mayor confirmación");
    } else if (profile.trading_goal === "speculation" && decision === "BUY" && conf >= 0.7) {
      parts.push("🎲 Coincide con tu objetivo especulativo");
    }

    // Experience reference
    if (profile.experience_level === "beginner" && decision === "BUY") {
      parts.push("📚 Como principiante, revisa el SL/TP antes de confirmar");
    } else if (profile.experience_level === "advanced" && decision === "BUY") {
      parts.push("🔬 Datos técnicos validados para tu nivel avanzado");
    }
  }

  return parts.join(", ") + (cleanExpl ? `. ${cleanExpl}` : ".");
}

function computePotentialReturn(signal: Signal): number | null {
  const entry = parseFloat(signal.entry_price || "0");
  const tp = parseFloat(signal.suggested_take_profit || "0");
  if (entry > 0 && tp > 0) {
    return ((tp - entry) / entry) * 100;
  }
  return null;
}

export function AISuggestionsPanel() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const { connectedAccounts, supportedBrokers } = useBrokerContext();

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [sigResp, profResp] = await Promise.all([
          api<Signal[]>("/api/signals?limit=50").catch(() => []),
          api<UserProfile>("/api/intelligence/profile").catch(() => null),
        ]);
        if (!alive) return;
        setSignals(sigResp);
        setProfile(profResp);
        setLoading(false);
      } catch {
        if (alive) setLoading(false);
      }
    };
    load();
    return () => { alive = false; };
  }, []);

  const connectedBrokers = connectedAccounts.filter((a) => isBrokerConnected(a.status));
  const hasConnectedBroker = connectedBrokers.length > 0;
  const primaryBrokerId = connectedBrokers[0]?.brokerId || supportedBrokers.find((b) => b.implemented)?.brokerId || "paper";

  const enriched: EnrichedSignal[] = signals
    .filter((s) => s.status === "active")
    .map((s) => {
      const conf = parseFloat(s.confidence);
      const { rating, score } = computeRating(conf);
      const horizon = inferTimeHorizon(s, profile);
      const potentialReturn = computePotentialReturn(s);
      return {
        ...s,
        rating,
        ratingScore: score,
        timeHorizon: horizon,
        timeHorizonLabel: HORIZON_LABELS[horizon],
        aiComment: generateAiComment(s, profile, horizon),
        riskMatch: profile ? (profile.risk_tolerance === "conservative" ? conf >= 0.7 : true) : true,
        potentialReturn,
      };
    })
    .sort((a, b) => b.ratingScore - a.ratingScore);

  const buySignals = enriched.filter((s) => s.signal_type === "BUY");
  const sellSignals = enriched.filter((s) => s.signal_type === "SELL");
  const holdSignals = enriched.filter((s) => s.signal_type === "HOLD");

  const handleTrade = (signal: EnrichedSignal) => {
    window.dispatchEvent(new CustomEvent("navigate", {
      detail: { page: "trade", asset: signal.symbol, broker: primaryBrokerId },
    }));
  };

  if (loading) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[13px] font-bold text-[var(--color-text)]">Sugerencias de Trading IA</h3>
        </div>
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  return (
    <div className="panel p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[13px] font-bold text-[var(--color-text)]">Sugerencias de Trading IA</h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-bold text-[var(--color-text-muted)]">
          <span className="px-2 h-5 rounded-[6px] bg-[var(--color-success)]/10 text-[var(--color-success)]">{buySignals.length} BUY</span>
          {sellSignals.length > 0 && <span className="px-2 h-5 rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)]">{sellSignals.length} SELL</span>}
          {holdSignals.length > 0 && <span className="px-2 h-5 rounded-[6px] bg-[var(--color-surface-2)]">{holdSignals.length} HOLD</span>}
        </div>
      </div>

      {/* Profile context */}
      {profile && (
        <div className="flex items-center gap-2 flex-wrap text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface-2)] rounded-[8px] px-3 py-2">
          <Shield size={11} className="flex-shrink-0" />
          <span>Perfil: <b className="text-[var(--color-text)]">{profile.experience_level}</b></span>
          <span>·</span>
          <span>Riesgo: <b className="text-[var(--color-text)]">{profile.risk_tolerance}</b></span>
          <span>·</span>
          <span>Capital: <b className="text-[var(--color-text)]">{profile.capital_range}</b></span>
          <span>·</span>
          <span>Estrategia: <b className="text-[var(--color-text)]">{profile.preferred_strategies.join(", ")}</b></span>
          <span>·</span>
          <span>Broker: <b className="text-[var(--color-text)]">{connectedBrokers.map(b => b.brokerId).join(", ") || "sin conectar"}</b></span>
        </div>
      )}

      {/* No connected broker warning */}
      {!hasConnectedBroker && (
        <div className="rounded-[8px] bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 px-3 py-2 text-[11px] text-[var(--color-warning)]">
          ⚠️ Conecta un broker para ejecutar trades directamente desde las sugerencias.
        </div>
      )}

      {/* Signals list */}
      {enriched.length === 0 ? (
        <div className="text-center py-6">
          <Sparkles size={24} className="mx-auto text-[var(--color-text-muted)] mb-2" />
          <p className="text-[12px] font-bold text-[var(--color-text)]">Sin sugerencias activas</p>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-1">El agente de IA generará sugerencias cuando detecte oportunidades.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {enriched.map((s, idx) => {
            const isBuy = s.signal_type === "BUY";
            const isSell = s.signal_type === "SELL";
            const decisionColor = isBuy ? "var(--color-success)" : isSell ? "var(--color-danger)" : "var(--color-text-muted)";
            const DecisionIcon = isBuy ? TrendingUp : isSell ? TrendingDown : Minus;

            return (
              <div
                key={s.id}
                className={cn(
                  "rounded-[10px] border p-3 space-y-2 transition-all",
                  isBuy ? "border-[var(--color-success)]/20 bg-[var(--color-success)]/5" :
                  isSell ? "border-[var(--color-danger)]/20 bg-[var(--color-danger)]/5" :
                  "border-[var(--color-border)] bg-[var(--color-surface-2)]"
                )}
              >
                {/* Top row: rank + symbol + decision + rating */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-extrabold text-[var(--color-text-muted)] w-5">#{idx + 1}</span>
                  <CryptoIcon symbol={s.symbol} size={20} />
                  <DecisionIcon size={14} style={{ color: decisionColor }} className="flex-shrink-0" />
                  <span className="text-[13px] font-extrabold text-[var(--color-text)] flex-1">{s.symbol}</span>
                  <span className={cn("text-[11px] font-extrabold", RATING_COLORS[s.rating])}>{s.rating}</span>
                  <span className="text-[10px] text-[var(--color-text-muted)]">{s.ratingScore.toFixed(0)}%</span>
                </div>

                {/* Second row: time horizon + potential return + SL/TP */}
                <div className="flex items-center gap-3 flex-wrap text-[10px]">
                  <span className="flex items-center gap-1 text-[var(--color-text-muted)]">
                    <Clock size={10} />
                    {HORIZON_ICONS[s.timeHorizon]} {s.timeHorizonLabel}
                  </span>
                  {s.potentialReturn !== null && (
                    <span className={cn("font-bold", s.potentialReturn >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      Retorno potencial: {s.potentialReturn >= 0 ? "+" : ""}{s.potentialReturn.toFixed(1)}%
                    </span>
                  )}
                  {s.entry_price && (
                    <span className="text-[var(--color-text-muted)]">
                      Entry: <b className="text-[var(--color-text)]">{fmt(parseFloat(s.entry_price))}</b>
                    </span>
                  )}
                  {s.suggested_stop_loss && (
                    <span className="text-[var(--color-danger)]">
                      SL: {fmt(parseFloat(s.suggested_stop_loss))}
                    </span>
                  )}
                  {s.suggested_take_profit && (
                    <span className="text-[var(--color-success)]">
                      TP: {fmt(parseFloat(s.suggested_take_profit))}
                    </span>
                  )}
                </div>

                {/* AI comment */}
                <div className="flex items-start gap-1.5 text-[11px] text-[var(--color-text)] bg-[var(--color-surface)] rounded-[6px] px-2.5 py-1.5">
                  <Sparkles size={11} className="text-[var(--color-primary)] flex-shrink-0 mt-0.5" />
                  <span>{s.aiComment}</span>
                </div>

                {/* Bottom row: timestamp + trade button */}
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-[var(--color-text-muted)]">{fmtDate(s.timestamp)}</span>
                  <button
                    onClick={() => handleTrade(s)}
                    disabled={!hasConnectedBroker}
                    className={cn(
                      "flex items-center gap-1.5 px-3 h-7 rounded-[8px] text-[11px] font-bold transition-all",
                      hasConnectedBroker
                        ? isBuy
                          ? "bg-[var(--color-success)] text-white hover:opacity-90"
                          : isSell
                            ? "bg-[var(--color-danger)] text-white hover:opacity-90"
                            : "bg-[var(--color-primary)] text-white hover:opacity-90"
                        : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                    )}
                  >
                    {isBuy ? "Comprar" : isSell ? "Vender" : "Ver"}
                    <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
