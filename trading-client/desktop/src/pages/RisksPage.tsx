import { useEffect, useState, useCallback } from "react";
import { TrendingDown, Waves, AlertTriangle, Zap, Shield, ShieldAlert, Bell } from "lucide-react";
import { CrashRiskGauge } from "../components/intelligence/CrashRiskGauge";
import { WhaleFeed } from "../components/intelligence/WhaleFeed";
import { AlertList } from "../components/intelligence/AlertList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getAlerts, getWhaleActivity, getNews } from "../lib/intelligenceApi";
import { api } from "../lib/api";
import type { IntelligenceAlert, WhaleActivity, NewsItem } from "../lib/intelligenceTypes";
import { cn } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { Tooltip, InfoPanel } from "../components/common/Tooltip";
import { PriceAlertsContent } from "./AlertsPage";

interface RiskConfig {
  trailing_stop_pct: number;
  hard_stop_loss_pct: number;
  take_profit_pct: number;
  max_position_size_pct: number;
  max_open_positions: number;
  daily_loss_limit_pct: number;
  circuit_breaker_enabled: boolean;
  auto_sell_rsi_overbought: number;
  auto_sell_max_position_hours: number;
  auto_sell_min_volume_relative: number;
  auto_sell_macd_bearish: boolean;
  auto_sell_rsi_enabled: boolean;
  auto_sell_time_enabled: boolean;
  auto_sell_volume_enabled: boolean;
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
  const [innerTab, setInnerTab] = useState<"risk" | "portfolio" | "price-alerts">("risk");

  return (
    <div className="p-5 space-y-4 max-w-[900px] mx-auto">
      <InfoPanel title="Que puedes hacer aqui" className="mb-4">
        <p><strong>Riesgos de Mercado:</strong> Monitorea crash risk, movimientos whale, y noticias de alto impacto que pueden afectar tus posiciones.</p>
        <p><strong>Portfolio Risk:</strong> Analiza correlacion entre posiciones, Value at Risk (VaR), y exposure por categoria. Muestra un risk score 0-100.</p>
        <p><strong>Alertas de Precio:</strong> Crea alertas que te avisan cuando un precio sube o baja de un nivel especifico.</p>
        <p><strong>Gestion de Riesgo:</strong> Configura stop loss automatico, circuit breaker, y indicadores tecnicos de auto-venta.</p>
      </InfoPanel>

      {/* Inner Tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border)]">
        <Tooltip text="Crash risk, whales, noticias de alto impacto">
          <button
            onClick={() => setInnerTab("risk")}
            className={cn(
              "flex items-center gap-1.5 px-3 h-9 text-[12px] font-bold border-b-2 transition-colors",
              innerTab === "risk"
                ? "border-[var(--color-primary)] text-[var(--color-text)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            )}
          >
            <ShieldAlert size={14} />
            Riesgos de Mercado
          </button>
        </Tooltip>
        <Tooltip text="Correlacion, VaR, exposure por categoria, risk score">
          <button
            onClick={() => setInnerTab("portfolio")}
            className={cn(
              "flex items-center gap-1.5 px-3 h-9 text-[12px] font-bold border-b-2 transition-colors",
              innerTab === "portfolio"
                ? "border-[var(--color-primary)] text-[var(--color-text)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            )}
          >
            <Shield size={14} />
            Portfolio Risk
          </button>
        </Tooltip>
        <Tooltip text="Crea y gestiona alertas de precio">
          <button
            onClick={() => setInnerTab("price-alerts")}
            className={cn(
              "flex items-center gap-1.5 px-3 h-9 text-[12px] font-bold border-b-2 transition-colors",
              innerTab === "price-alerts"
                ? "border-[var(--color-primary)] text-[var(--color-text)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            )}
          >
            <Bell size={14} />
            Alertas de Precio
          </button>
        </Tooltip>
      </div>

      {innerTab === "risk" ? (
        <RisksPageContent />
      ) : innerTab === "portfolio" ? (
        <PortfolioRiskContent />
      ) : (
        <PriceAlertsContent />
      )}
    </div>
  );
}

function RisksPageContent() {
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
    <div className="space-y-4">
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
          <>
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

          {/* Auto-Sell Technical Thresholds */}
          <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
            <h4 className="text-[12px] font-bold text-[var(--color-primary)] uppercase mb-3 flex items-center gap-2">
              <Zap size={12} />
              Auto-Sell Technical Indicators
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <RiskInput
                label="RSI Overbought"
                value={riskConfig.auto_sell_rsi_overbought ?? 70}
                step={1}
                onSave={(v) => handleSaveConfig({ auto_sell_rsi_overbought: v })}
                saving={savingConfig}
              />
              <RiskInput
                label="Max Position Hours"
                value={riskConfig.auto_sell_max_position_hours ?? 24}
                step={1}
                onSave={(v) => handleSaveConfig({ auto_sell_max_position_hours: v })}
                saving={savingConfig}
              />
              <RiskInput
                label="Min Volume Relative"
                value={riskConfig.auto_sell_min_volume_relative ?? 0.5}
                step={0.1}
                onSave={(v) => handleSaveConfig({ auto_sell_min_volume_relative: v })}
                saving={savingConfig}
              />
            </div>
            <div className="flex flex-wrap gap-4 mt-3">
              <RiskToggle
                label="RSI Enabled"
                value={riskConfig.auto_sell_rsi_enabled ?? true}
                onSave={(v) => handleSaveConfig({ auto_sell_rsi_enabled: v })}
                saving={savingConfig}
              />
              <RiskToggle
                label="MACD Bearish"
                value={riskConfig.auto_sell_macd_bearish ?? true}
                onSave={(v) => handleSaveConfig({ auto_sell_macd_bearish: v })}
                saving={savingConfig}
              />
              <RiskToggle
                label="Time Exit"
                value={riskConfig.auto_sell_time_enabled ?? true}
                onSave={(v) => handleSaveConfig({ auto_sell_time_enabled: v })}
                saving={savingConfig}
              />
              <RiskToggle
                label="Volume Exit"
                value={riskConfig.auto_sell_volume_enabled ?? true}
                onSave={(v) => handleSaveConfig({ auto_sell_volume_enabled: v })}
                saving={savingConfig}
              />
            </div>
          </div>
          </>
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
                      <td className="py-1.5 font-bold text-[var(--color-text)]">
                        <div className="flex items-center gap-1.5">
                          <CryptoIcon symbol={p.symbol} size={18} />
                          {p.symbol}
                        </div>
                      </td>
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

function RiskInput({ label, value, step, onSave, saving }: {
  label: string;
  value: number;
  step: number;
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

function RiskToggle({ label, value, onSave, saving }: {
  label: string;
  value: boolean;
  onSave: (v: boolean) => void;
  saving: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">{label}</span>
      <button
        onClick={() => !saving && onSave(!value)}
        disabled={saving}
        className={cn(
          "px-2 h-6 rounded-[6px] text-[10px] font-bold transition-colors",
          value
            ? "bg-[var(--color-success)] text-white"
            : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
        )}
      >
        {value ? "ON" : "OFF"}
      </button>
    </div>
  );
}

// ─── Portfolio Risk Content ───────────────────────────────────────────────────

interface PortfolioRiskData {
  total_exposure: number;
  max_single_position_pct: number;
  category_exposure: Record<string, number>;
  category_limits: Record<string, number>;
  category_warnings: string[];
  correlation_warnings: string[];
  correlation_matrix: Record<string, Record<string, number>>;
  avg_correlation: number;
  var: {
    var_95_pct: number;
    var_99_pct: number;
    cvar_95_pct: number;
    var_95_usd: number;
    var_99_usd: number;
    cvar_95_usd: number;
    portfolio_value: number;
  } | null;
  risk_score: number;
  recommendations: string[];
  positions: {
    symbol: string;
    quantity: number;
    entry_price: number;
    current_price: number;
    value: number;
    unrealized_pnl: number;
  }[];
  portfolio_value: number;
  cash: number;
}

function PortfolioRiskContent() {
  const [data, setData] = useState<PortfolioRiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await api<PortfolioRiskData>("/api/portfolio-risk");
      setData(r);
    } catch (e: any) {
      setError(e.message || "Error al cargar portfolio risk");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <div className="text-[var(--color-danger)] text-[13px]">{error}</div>;
  if (!data) return null;

  const riskColor =
    data.risk_score < 30 ? "var(--color-success)" :
    data.risk_score < 60 ? "var(--color-warning)" :
    "var(--color-danger)";

  const riskLabel =
    data.risk_score < 30 ? "Bajo" :
    data.risk_score < 60 ? "Moderado" :
    "Alto";

  return (
    <div className="space-y-4">
      {/* Risk Score Banner */}
      <div className="panel p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Risk Score</div>
            <div className="text-[32px] font-extrabold" style={{ color: riskColor }}>
              {data.risk_score}<span className="text-[16px] text-[var(--color-text-muted)]">/100</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Nivel</div>
            <div className="text-[20px] font-bold" style={{ color: riskColor }}>{riskLabel}</div>
          </div>
          <Tooltip text="Recarga todos los datos de riesgo desde el servidor">
            <button
              onClick={load}
              className="ml-auto h-8 px-3 rounded-[8px] bg-[var(--color-surface-2)] text-[11px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              Actualizar
            </button>
          </Tooltip>
        </div>
        {/* Risk score bar */}
        <div className="h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${data.risk_score}%`, backgroundColor: riskColor }}
          />
        </div>
      </div>

      {/* VaR + Exposure Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="panel p-3">
          <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Portfolio Value</div>
          <div className="text-[18px] font-extrabold text-[var(--color-text)]">${data.portfolio_value?.toFixed(0)}</div>
        </div>
        <div className="panel p-3">
          <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Total Exposure</div>
          <div className="text-[18px] font-extrabold text-[var(--color-text)]">${data.total_exposure?.toFixed(0)}</div>
        </div>
        <div className="panel p-3">
          <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Cash Available</div>
          <div className="text-[18px] font-extrabold text-[var(--color-success)]">${data.cash?.toFixed(0)}</div>
        </div>
        <div className="panel p-3">
          <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Max Position</div>
          <div className="text-[18px] font-extrabold text-[var(--color-text)]">{data.max_single_position_pct?.toFixed(1)}%</div>
        </div>
      </div>

      {/* VaR Cards */}
      {data.var && (
        <div className="panel p-5">
          <h3 className="text-[14px] font-extrabold text-[var(--color-text)] mb-3">Value at Risk (VaR)</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3">
              <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">95% VaR (1 dia)</div>
              <div className="text-[20px] font-extrabold text-[var(--color-warning)]">${data.var.var_95_usd.toFixed(0)}</div>
              <div className="text-[10px] text-[var(--color-text-muted)]">{data.var.var_95_pct}% del portfolio</div>
            </div>
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3">
              <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">99% VaR (1 dia)</div>
              <div className="text-[20px] font-extrabold text-[var(--color-danger)]">${data.var.var_99_usd.toFixed(0)}</div>
              <div className="text-[10px] text-[var(--color-text-muted)]">{data.var.var_99_pct}% del portfolio</div>
            </div>
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3">
              <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-1">CVaR (Expected Shortfall)</div>
              <div className="text-[20px] font-extrabold text-[var(--color-danger)]">${data.var.cvar_95_usd.toFixed(0)}</div>
              <div className="text-[10px] text-[var(--color-text-muted)]">{data.var.cvar_95_pct}% del portfolio</div>
            </div>
          </div>
          <div className="mt-3 text-[11px] text-[var(--color-text-muted)]">
            95% VaR: hay 95% de probabilidad de no perder mas de ${data.var.var_95_usd.toFixed(0)} en un dia.
            CVaR: si se supera el 5%, el promedio de perdida seria ${data.var.cvar_95_usd.toFixed(0)}.
          </div>
        </div>
      )}

      {/* Category Exposure */}
      <div className="panel p-5">
        <h3 className="text-[14px] font-extrabold text-[var(--color-text)] mb-3">Exposicion por Categoria</h3>
        <div className="space-y-2">
          {Object.entries(data.category_exposure).map(([cat, pct]) => {
            const limit = data.category_limits[cat] || 50;
            const overLimit = pct > limit;
            return (
              <div key={cat}>
                <div className="flex items-center justify-between text-[12px] mb-1">
                  <span className="font-bold text-[var(--color-text)] capitalize">{cat}</span>
                  <span className={cn("font-bold", overLimit ? "text-[var(--color-danger)]" : "text-[var(--color-text-muted)]")}>
                    {pct.toFixed(1)}% / {limit}% {overLimit && "⚠"}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all", overLimit ? "bg-[var(--color-danger)]" : "bg-[var(--color-primary)]")}
                    style={{ width: `${Math.min(pct / limit * 100, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
          {Object.keys(data.category_exposure).length === 0 && (
            <div className="text-[12px] text-[var(--color-text-muted)]">No hay posiciones abiertas</div>
          )}
        </div>
      </div>

      {/* Correlation Matrix */}
      {Object.keys(data.correlation_matrix).length > 1 && (
        <div className="panel p-5">
          <h3 className="text-[14px] font-extrabold text-[var(--color-text)] mb-3">
            Matriz de Correlacion
            <span className="ml-2 text-[11px] font-normal text-[var(--color-text-muted)]">
              Promedio: {data.avg_correlation.toFixed(2)}
            </span>
          </h3>
          <div className="overflow-x-auto">
            <table className="text-[11px]">
              <thead>
                <tr>
                  <th className="text-left p-1 text-[var(--color-text-muted)]"></th>
                  {Object.keys(data.correlation_matrix).map(col => (
                    <th key={col} className="text-center p-1 text-[var(--color-text-muted)] font-bold">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.correlation_matrix).map(([row, cols]) => (
                  <tr key={row}>
                    <td className="text-left p-1 text-[var(--color-text-muted)] font-bold">{row}</td>
                    {Object.keys(data.correlation_matrix).map(col => {
                      const val = cols[col] ?? 0;
                      const color = val > 0.85 ? "var(--color-danger)" : val > 0.7 ? "var(--color-warning)" : val > 0.4 ? "var(--color-primary)" : "var(--color-text-muted)";
                      return (
                        <td
                          key={col}
                          className="text-center p-1 font-bold"
                          style={{ color: val >= 1 ? "var(--color-text)" : color }}
                        >
                          {val.toFixed(2)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.correlation_warnings.length > 0 && (
            <div className="mt-3 space-y-1">
              {data.correlation_warnings.map((w, i) => (
                <div key={i} className="text-[11px] text-[var(--color-warning)] flex items-center gap-1">
                  <AlertTriangle size={11} /> {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Warnings */}
      {(data.category_warnings.length > 0 || data.correlation_warnings.length > 0) && (
        <div className="panel p-5 border border-[var(--color-warning)]/30">
          <h3 className="text-[14px] font-extrabold text-[var(--color-warning)] mb-3 flex items-center gap-2">
            <AlertTriangle size={16} /> Alertas
          </h3>
          <div className="space-y-1">
            {data.category_warnings.map((w, i) => (
              <div key={`cat-${i}`} className="text-[12px] text-[var(--color-text-muted)]">• {w}</div>
            ))}
            {data.correlation_warnings.map((w, i) => (
              <div key={`corr-${i}`} className="text-[12px] text-[var(--color-text-muted)]">• {w}</div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      <div className="panel p-5">
        <h3 className="text-[14px] font-extrabold text-[var(--color-text)] mb-3">Recomendaciones</h3>
        <div className="space-y-2">
          {data.recommendations.map((r, i) => (
            <div key={i} className="text-[12px] text-[var(--color-text-muted)] flex items-start gap-2">
              <span className="text-[var(--color-primary)] font-bold">→</span>
              {r}
            </div>
          ))}
        </div>
      </div>

      {/* Positions */}
      {data.positions.length > 0 && (
        <div className="panel p-5">
          <h3 className="text-[14px] font-extrabold text-[var(--color-text)] mb-3">
            Posiciones Abiertas ({data.positions.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                  <th className="text-left pb-2">Symbol</th>
                  <th className="text-right pb-2">Qty</th>
                  <th className="text-right pb-2">Entry</th>
                  <th className="text-right pb-2">Current</th>
                  <th className="text-right pb-2">Value</th>
                  <th className="text-right pb-2">PnL</th>
                  <th className="text-right pb-2">% Portfolio</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((p) => {
                  const pnlPct = p.unrealized_pnl > 0 ? "+" : "";
                  const portfolioPct = (p.value / data.portfolio_value * 100).toFixed(1);
                  return (
                    <tr key={p.symbol} className="border-b border-[var(--color-border)]/30">
                      <td className="py-1.5 font-bold text-[var(--color-text)]">{p.symbol}</td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">{p.quantity.toFixed(4)}</td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">${p.entry_price.toFixed(2)}</td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">${p.current_price.toFixed(2)}</td>
                      <td className="text-right py-1.5 font-bold text-[var(--color-text)]">${p.value.toFixed(0)}</td>
                      <td className={cn("text-right py-1.5 font-bold", p.unrealized_pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        {pnlPct}${p.unrealized_pnl.toFixed(2)}
                      </td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">{portfolioPct}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
