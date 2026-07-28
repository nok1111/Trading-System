import { useEffect, useState, useCallback } from "react";
import { TrendingDown, Waves, AlertTriangle, Zap, Shield } from "lucide-react";
import { CrashRiskGauge } from "../components/intelligence/CrashRiskGauge";
import { WhaleFeed } from "../components/intelligence/WhaleFeed";
import { AlertList } from "../components/intelligence/AlertList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getAlerts, getWhaleActivity, getNews } from "../lib/intelligenceApi";
import { api } from "../lib/api";
import type { IntelligenceAlert, WhaleActivity, NewsItem } from "../lib/intelligenceTypes";
import { cn } from "../lib/utils";

interface RiskConfig {
  trailing_stop_pct: number;
  hard_stop_loss_pct: number;
  take_profit_pct: number;
  max_position_size_pct: number;
  max_open_positions: number;
  daily_loss_limit_pct: number;
  circuit_breaker_enabled: boolean;
}

interface RiskStatus {
  open_positions: number;
  max_open_positions: number;
  total_exposure: number;
  total_unrealized_pnl: number;
  daily_loss_pct: number;
  daily_loss_limit_pct: number;
  circuit_breaker_enabled: boolean;
  circuit_breaker_triggered: boolean;
  positions: {
    symbol: string;
    quantity: number;
    entry_price: number;
    current_price: number;
    unrealized_pnl: number;
    unrealized_pnl_pct: number;
  }[];
}

export function RisksPage() {
  const [alerts, setAlerts] = useState<IntelligenceAlert[]>([]);
  const [whales, setWhales] = useState<WhaleActivity[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [riskConfig, setRiskConfig] = useState<RiskConfig | null>(null);
  const [riskStatus, setRiskStatus] = useState<RiskStatus | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  const loadRisk = useCallback(async () => {
    const [cfg, status] = await Promise.all([
      api<RiskConfig>("/api/intelligence/risk/config").catch(() => null),
      api<RiskStatus>("/api/intelligence/risk/status").catch(() => null),
    ]);
    setRiskConfig(cfg);
    setRiskStatus(status);
  }, []);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [a, w, n] = await Promise.all([
        getAlerts(20),
        getWhaleActivity(15),
        getNews(20),
      ]);
      if (!alive) return;
      setAlerts(a);
      setWhales(w);
      setNews(n);
      setLoading(false);
    };
    load();
    loadRisk();
    const id = setInterval(loadRisk, 30000);
    return () => { alive = false; clearInterval(id); };
  }, [loadRisk]);

  const handleSaveConfig = async (updates: Partial<RiskConfig>) => {
    setSavingConfig(true);
    try {
      const r = await api<{ config: RiskConfig }>("/api/intelligence/risk/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      setRiskConfig(r.config);
      await loadRisk();
    } catch {
      // ignore
    }
    setSavingConfig(false);
  };

  const crashRisk = alerts.find((a) => a.crashRisk != null)?.crashRisk ?? null;
  const highImpactNews = news.filter((n) => n.impact === "high");
  const largeWhales = whales.filter((w) => w.amountUsd >= 500000);

  return (
    <div className="p-5 space-y-4 max-w-[900px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-[var(--color-warning)]" />
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Alertas de Mercado</h2>
      </div>

      {/* Crash Risk + Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
            <TrendingDown size={14} className="text-[var(--color-danger)]" />
            Crash Risk
          </h3>
          {loading ? <LoadingSkeleton lines={3} /> : <CrashRiskGauge crashRisk={crashRisk} />}
        </div>
        <div className="panel p-4 space-y-2">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-1 flex items-center gap-2">
            <Waves size={14} className="text-[var(--color-primary)]" />
            Whale Alerts
          </h3>
          <div className="text-[24px] font-extrabold text-[var(--color-text)]">{largeWhales.length}</div>
          <p className="text-[10px] text-[var(--color-text-muted)]">Movimientos &gt; $500K detectados</p>
        </div>
        <div className="panel p-4 space-y-2">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-1 flex items-center gap-2">
            <AlertTriangle size={14} className="text-[var(--color-warning)]" />
            Noticias de Alto Impacto
          </h3>
          <div className="text-[24px] font-extrabold text-[var(--color-text)]">{highImpactNews.length}</div>
          <p className="text-[10px] text-[var(--color-text-muted)]">Eventos que pueden mover el mercado</p>
        </div>
      </div>

      {/* High-impact news */}
      {highImpactNews.length > 0 && (
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
            <AlertTriangle size={14} className="text-[var(--color-warning)]" />
            Noticias de Alto Impacto
          </h3>
          <div className="space-y-2">
            {highImpactNews.map((n) => (
              <a
                key={n.id}
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-warning)]/30 border-l-3 border-l-[var(--color-warning)] p-3 hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] font-bold text-[var(--color-text)]">{n.source}</span>
                  <span className={cn(
                    "text-[10px] font-bold uppercase px-2 h-5 rounded flex items-center",
                    n.sentiment === "negative" ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]" :
                    n.sentiment === "positive" ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" :
                    "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                  )}>
                    {n.sentiment}
                  </span>
                </div>
                <p className="text-[12px] text-[var(--color-text)] font-semibold">{n.title}</p>
                {n.summary && <p className="text-[11px] text-[var(--color-text-muted)] mt-1 line-clamp-2">{n.summary}</p>}
                {n.assets.length > 0 && (
                  <div className="flex gap-1 mt-2">
                    {n.assets.slice(0, 5).map((a) => (
                      <span key={a} className="text-[10px] font-bold px-1.5 h-4 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] flex items-center">
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Large whale movements */}
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
          <Waves size={14} className="text-[var(--color-primary)]" />
          Movimientos Whale Grandes
        </h3>
        {loading ? <LoadingSkeleton lines={4} /> : <WhaleFeed activities={largeWhales.length > 0 ? largeWhales : whales} />}
      </div>

      {/* Risk alerts */}
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
          <AlertTriangle size={14} className="text-[var(--color-danger)]" />
          Alertas de Riesgo Activas
        </h3>
        {loading ? <LoadingSkeleton lines={4} /> : <AlertList alerts={alerts} />}
      </div>

      {/* Risk Management Panel */}
      <div className="panel p-5">
        <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-4 flex items-center gap-2">
          <Shield size={16} className="text-[var(--color-primary)]" />
          Gestión de Riesgo
        </h3>

        {/* Circuit breaker status */}
        {riskStatus && (
          <div className={cn(
            "rounded-[10px] p-3 mb-4 border",
            riskStatus.circuit_breaker_triggered
              ? "bg-[var(--color-danger)]/10 border-[var(--color-danger)]/30"
              : "bg-[var(--color-success)]/10 border-[var(--color-success)]/30"
          )}>
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-bold text-[var(--color-text)]">
                Circuit Breaker: {riskStatus.circuit_breaker_triggered ? "ACTIVADO" : "OK"}
              </span>
              <span className="text-[11px] text-[var(--color-text-muted)]">
                Pérdida diaria: {riskStatus.daily_loss_pct.toFixed(2)}% / {riskStatus.daily_loss_limit_pct}% límite
              </span>
            </div>
          </div>
        )}

        {/* Risk config inputs */}
        {riskConfig && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            <RiskInput
              label="Trailing Stop %"
              value={riskConfig.trailing_stop_pct}
              step={0.5}
              onSave={(v) => handleSaveConfig({ trailing_stop_pct: v })}
              saving={savingConfig}
            />
            <RiskInput
              label="Stop-Loss %"
              value={riskConfig.hard_stop_loss_pct}
              step={0.5}
              onSave={(v) => handleSaveConfig({ hard_stop_loss_pct: v })}
              saving={savingConfig}
            />
            <RiskInput
              label="Take-Profit %"
              value={riskConfig.take_profit_pct}
              step={0.5}
              onSave={(v) => handleSaveConfig({ take_profit_pct: v })}
              saving={savingConfig}
            />
            <RiskInput
              label="Max Position Size %"
              value={riskConfig.max_position_size_pct}
              step={1}
              onSave={(v) => handleSaveConfig({ max_position_size_pct: v })}
              saving={savingConfig}
            />
            <RiskInput
              label="Max Open Positions"
              value={riskConfig.max_open_positions}
              step={1}
              isInt={true}
              onSave={(v) => handleSaveConfig({ max_open_positions: Math.round(v) })}
              saving={savingConfig}
            />
            <RiskInput
              label="Daily Loss Limit %"
              value={riskConfig.daily_loss_limit_pct}
              step={0.5}
              onSave={(v) => handleSaveConfig({ daily_loss_limit_pct: v })}
              saving={savingConfig}
            />
          </div>
        )}

        {/* Position risk table */}
        {riskStatus && riskStatus.positions.length > 0 && (
          <div>
            <h4 className="text-[12px] font-bold text-[var(--color-text-muted)] uppercase mb-2">
              Posiciones Abiertas ({riskStatus.open_positions}/{riskStatus.max_open_positions})
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="text-left pb-2">Símbolo</th>
                    <th className="text-right pb-2">Cantidad</th>
                    <th className="text-right pb-2">Entry</th>
                    <th className="text-right pb-2">Actual</th>
                    <th className="text-right pb-2">PnL</th>
                    <th className="text-right pb-2">PnL %</th>
                  </tr>
                </thead>
                <tbody>
                  {riskStatus.positions.map((p, i) => (
                    <tr key={i} className="border-b border-[var(--color-border)]/30">
                      <td className="py-1.5 font-bold text-[var(--color-text)]">{p.symbol}</td>
                      <td className="text-right text-[var(--color-text-muted)]">{p.quantity.toFixed(6)}</td>
                      <td className="text-right text-[var(--color-text-muted)]">${p.entry_price.toFixed(4)}</td>
                      <td className="text-right text-[var(--color-text-muted)]">${p.current_price.toFixed(4)}</td>
                      <td className={cn("text-right font-bold", p.unrealized_pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        ${p.unrealized_pnl.toFixed(2)}
                      </td>
                      <td className={cn("text-right font-bold", p.unrealized_pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        {p.unrealized_pnl_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-2 flex justify-between text-[11px] text-[var(--color-text-muted)]">
              <span>Exposición total: ${riskStatus.total_exposure.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
              <span>PnL total: <span className={riskStatus.total_unrealized_pnl >= 0 ? "text-[var(--color-success)] font-bold" : "text-[var(--color-danger)] font-bold"}>
                ${riskStatus.total_unrealized_pnl.toLocaleString("en-US", { maximumFractionDigits: 2 })}
              </span></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RiskInput({ label, value, step, isInt, onSave, saving }: {
  label: string;
  value: number;
  step: number;
  isInt?: boolean;
  onSave: (v: number) => void;
  saving: boolean;
}) {
  const [localValue, setLocalValue] = useState(String(value));
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLocalValue(String(value));
    setDirty(false);
  }, [value]);

  return (
    <div>
      <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">{label}</label>
      <div className="flex gap-1">
        <input
          type="number"
          value={localValue}
          onChange={(e) => { setLocalValue(e.target.value); setDirty(true); }}
          step={step}
          className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
        />
        <button
          onClick={() => dirty && onSave(parseFloat(localValue))}
          disabled={!dirty || saving}
          className={cn(
            "px-2 h-8 rounded-[6px] text-[11px] font-bold transition-colors shrink-0",
            dirty && !saving
              ? "bg-[var(--color-primary)] text-white hover:opacity-90"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
          )}
        >
          OK
        </button>
      </div>
    </div>
  );
}
