import { useEffect, useState, useMemo } from "react";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getReports } from "../lib/intelligenceApi";
import { CryptoIcon } from "../components/CryptoIcon";
import { cn } from "../lib/utils";
import type { IntelligenceReport } from "../lib/intelligenceTypes";

const ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX"];

interface ReportItem extends IntelligenceReport {
  action_type?: string;
  confidence?: number;
  status?: string;
  trading_mode?: string | null;
  broker_name?: string | null;
}

export function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [asset, setAsset] = useState("BTC");
  const [typeFilter, setTypeFilter] = useState<"all" | "daily" | "weekly" | "monthly">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      setLoading(true);
      try {
        const r = await getReports(asset);
        if (!alive) return;
        setReports(r as ReportItem[]);
      } catch { /* ignore */ }
      if (alive) setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, [asset]);

  const filtered = useMemo(() => {
    return typeFilter === "all" ? reports : reports.filter((r) => r.type === typeFilter);
  }, [reports, typeFilter]);

  const typeBtn = (active: boolean) =>
    cn("px-2.5 h-7 rounded-[6px] text-[11px] font-bold transition-colors", active ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]");

  const actionBadge = (action?: string) => {
    if (!action) return null;
    if (action === "BUY") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-success)] text-white">COMPRA</span>;
    if (action === "SELL") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-danger)] text-white">VENTA</span>;
    return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">HOLD</span>;
  };

  const statusBadge = (status?: string) => {
    if (!status || status === "pending") return <span className="text-[9px] text-[var(--color-text-muted)]">Pendiente</span>;
    if (status === "executed") return <span className="text-[9px] text-[var(--color-success)] font-bold">Ejecutada</span>;
    if (status === "dismissed") return <span className="text-[9px] text-[var(--color-text-muted)] line-through">Descartada</span>;
    return null;
  };

  const modeBadge = (mode?: string | null, broker?: string | null) => {
    if (!mode) return null;
    if (mode === "paper") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-info)] text-white">PAPER MONEY</span>;
    if (mode === "live") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-success)] text-white">{(broker || "LIVE").toUpperCase()}</span>;
    return null;
  };

  const cardBorder = (mode?: string | null) => {
    if (mode === "paper") return "border-l-[3px] border-l-[var(--color-info)]";
    if (mode === "live") return "border-l-[3px] border-l-[var(--color-success)]";
    return "";
  };

  return (
    <div className="p-5 max-w-[800px] mx-auto space-y-4">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Reportes & Recomendaciones</h2>

      {/* Asset selector */}
      <div className="flex gap-1.5 flex-wrap">
        {ASSETS.map((a) => (
          <button
            key={a}
            onClick={() => setAsset(a)}
            className={cn(
              "px-2.5 h-8 rounded-[8px] text-[12px] font-bold transition-colors flex items-center gap-1.5",
              asset === a ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            )}
          >
            <CryptoIcon symbol={a + "USDT"} size={16} />
            {a}
          </button>
        ))}
      </div>

      {/* Type filter */}
      <div className="flex gap-1">
        <button className={typeBtn(typeFilter === "all")} onClick={() => setTypeFilter("all")}>Todos</button>
        <button className={typeBtn(typeFilter === "daily")} onClick={() => setTypeFilter("daily")}>Diarios</button>
        <button className={typeBtn(typeFilter === "weekly")} onClick={() => setTypeFilter("weekly")}>Semanales</button>
        <button className={typeBtn(typeFilter === "monthly")} onClick={() => setTypeFilter("monthly")}>Mensuales</button>
      </div>

      <div className="text-[11px] text-[var(--color-text-muted)]">
        {filtered.length} reportes para {asset}
      </div>

      {loading ? (
        <LoadingSkeleton lines={4} />
      ) : filtered.length === 0 ? (
        <div className="text-center py-8 text-[12px] text-[var(--color-text-muted)]">
          No hay reportes disponibles para {asset}.
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((r) => {
            const isExpanded = expandedId === r.id;
            return (
              <div
                key={r.id}
                className={cn(
                  "rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 cursor-pointer hover:border-[var(--color-border-strong)] transition-colors",
                  cardBorder(r.trading_mode)
                )}
                onClick={() => setExpandedId(isExpanded ? null : r.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CryptoIcon symbol={r.asset + "USDT"} size={20} />
                    <span className="text-[13px] font-bold text-[var(--color-text)]">
                      {r.type === "daily" ? "Daily" : r.type === "weekly" ? "Weekly" : "Monthly"} — {r.asset}
                    </span>
                    {actionBadge(r.action_type)}
                    {r.confidence != null && (
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        {Math.round(r.confidence * 100)}% confianza
                      </span>
                    )}
                    {modeBadge(r.trading_mode, r.broker_name)}
                  </div>
                  <div className="flex items-center gap-2">
                    {statusBadge(r.status)}
                    <span className="text-[10px] text-[var(--color-text-muted)]">{r.date}</span>
                  </div>
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{r.summary}</p>
                {isExpanded && r.sections && (
                  <div className="mt-3 space-y-2 border-t border-[var(--color-border)] pt-3">
                    {r.sections.marketOverview && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Market Overview</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.marketOverview}</p>
                      </div>
                    )}
                    {r.sections.keyEvents && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Recomendación</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.keyEvents}</p>
                      </div>
                    )}
                    {r.sections.performance && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Gestión de riesgo</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.performance}</p>
                      </div>
                    )}
                    {r.sections.outlook && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Razón</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.outlook}</p>
                      </div>
                    )}
                  </div>
                )}
                {!isExpanded && (
                  <div className="text-[10px] text-[var(--color-text-muted)] mt-1">Click para expandir ▼</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
