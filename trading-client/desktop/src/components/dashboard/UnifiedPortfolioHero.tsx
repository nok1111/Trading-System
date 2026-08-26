import { useEffect, useState, useCallback } from "react";
import { Wallet, TrendingUp, TrendingDown, AlertTriangle, RefreshCw, Building2 } from "lucide-react";
import {
  getPortfolioOverview,
  type PortfolioOverview,
} from "../../lib/portfolioApi";

export function UnifiedPortfolioHero() {
  const [data, setData] = useState<PortfolioOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const overview = await getPortfolioOverview();
      setData(overview);
    } catch (err: any) {
      setError(err.message || "Error al cargar portfolio");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="panel p-6 flex items-center justify-center min-h-[200px]">
        <div className="text-[var(--color-text-muted)] text-sm">Cargando portfolio unificado...</div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="panel p-6 flex items-center justify-center min-h-[200px]">
        <div className="text-[var(--color-danger)] text-sm">{error}</div>
      </div>
    );
  }

  if (!data) return null;

  const totalUsd = data.total_usd;
  const totalPnl = data.total_unrealized_pnl;
  const isPositive = totalPnl >= 0;

  return (
    <div className="space-y-3">
      {/* Main hero card */}
      <div className="panel p-6 bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-surface-2)]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Wallet size={20} className="text-[var(--color-primary)]" />
            <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Portfolio Unificado</h2>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-semibold">
              {data.broker_count} {data.broker_count === 1 ? "broker" : "brokers"}
            </span>
          </div>
          <button
            onClick={fetchData}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1.5 rounded hover:bg-[var(--color-surface-2)]"
            title="Actualizar"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {/* Total Value */}
          <div>
            <div className="text-[11px] text-[var(--color-text-muted)] mb-1">Valor Total</div>
            <div className="text-[28px] font-extrabold text-[var(--color-text)]">
              ${totalUsd.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>

          {/* Unrealized PnL */}
          <div>
            <div className="text-[11px] text-[var(--color-text-muted)] mb-1">P&L No Realizado</div>
            <div className={`text-[28px] font-extrabold flex items-center gap-1 ${
              isPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
            }`}>
              {isPositive ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
              {isPositive ? "+" : ""}${totalPnl.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>

          {/* Positions Count */}
          <div>
            <div className="text-[11px] text-[var(--color-text-muted)] mb-1">Posiciones Abiertas</div>
            <div className="text-[28px] font-extrabold text-[var(--color-text)]">
              {data.position_count}
            </div>
          </div>
        </div>
      </div>

      {/* By Broker breakdown */}
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Building2 size={16} className="text-[var(--color-text-muted)]" />
          <h3 className="text-[13px] font-bold text-[var(--color-text)]">Por Broker</h3>
        </div>
        <div className="space-y-2">
          {data.balances.by_broker.map((broker) => {
            const pct = totalUsd > 0 ? (broker.total_usd / totalUsd) * 100 : 0;
            return (
              <div key={broker.broker_id} className="space-y-1">
                <div className="flex items-center justify-between text-[12px]">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[var(--color-text)]">{broker.display_name}</span>
                    {broker.error && (
                      <span className="text-[10px] text-[var(--color-danger)]">⚠ {broker.error.slice(0, 40)}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--color-text-muted)]">{pct.toFixed(1)}%</span>
                    <span className="font-bold text-[var(--color-text)]">
                      ${broker.total_usd.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[var(--color-primary)] transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Concentration warnings */}
      {data.concentration.warnings.length > 0 && (
        <div className="panel p-4 border border-[var(--color-warning)]/30">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-[var(--color-warning)]" />
            <h3 className="text-[13px] font-bold text-[var(--color-text)]">Alertas de Concentración</h3>
          </div>
          <div className="space-y-1.5">
            {data.concentration.warnings.map((w, i) => (
              <div
                key={i}
                className={`text-[12px] px-3 py-2 rounded-lg ${
                  w.level === "high"
                    ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]"
                    : "bg-[var(--color-warning)]/10 text-[var(--color-warning)]"
                }`}
              >
                {w.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
