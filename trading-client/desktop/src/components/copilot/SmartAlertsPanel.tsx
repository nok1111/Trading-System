import { useEffect, useState, useCallback } from "react";
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Shield,
  Target,
  Scale,
  Search,
  X,
  RefreshCw,
  Zap,
} from "lucide-react";
import {
  getSmartAlerts,
  dismissSmartAlert,
  type SmartAlert,
} from "../../lib/smartAlertsApi";

const ALERT_ICONS: Record<string, typeof AlertTriangle> = {
  high_loss: TrendingDown,
  high_gain: TrendingUp,
  concentration_risk: Scale,
  margin_call_risk: AlertTriangle,
  no_stop_loss: Shield,
  stablecoin_excess: Target,
  broker_error: AlertTriangle,
  market_regime_change: Zap,
  volatility_spike: Zap,
};

function getUrgencyColor(urgency: number): string {
  if (urgency >= 70) return "var(--color-danger)";
  if (urgency >= 40) return "var(--color-warning)";
  return "var(--color-text-muted)";
}

function getUrgencyLabel(urgency: number): string {
  if (urgency >= 70) return "Urgente";
  if (urgency >= 40) return "Media";
  return "Baja";
}

interface SmartAlertsPanelProps {
  onAction?: (action: { type: string; params: Record<string, unknown> }) => void;
  maxAlerts?: number;
}

export function SmartAlertsPanel({ onAction, maxAlerts = 10 }: SmartAlertsPanelProps) {
  const [alerts, setAlerts] = useState<SmartAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getSmartAlerts();
      setAlerts(result.alerts);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 120000); // refresh every 2 min
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleDismiss = async (alertId: string) => {
    setDismissed((prev) => new Set([...prev, alertId]));
    try {
      await dismissSmartAlert(alertId);
    } catch {
      // revert on error
      setDismissed((prev) => {
        const next = new Set(prev);
        next.delete(alertId);
        return next;
      });
    }
  };

  const visibleAlerts = alerts.filter((a) => !dismissed.has(a.id)).slice(0, maxAlerts);

  if (loading && alerts.length === 0) {
    return (
      <div className="panel p-4 min-h-[80px] flex items-center justify-center">
        <div className="text-[var(--color-text-muted)] text-[12px] flex items-center gap-2">
          <Zap size={14} className="animate-pulse" />
          Generando alertas inteligentes...
        </div>
      </div>
    );
  }

  if (visibleAlerts.length === 0) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-2">
          <Zap size={16} className="text-[var(--color-success)]" />
          <h3 className="text-[13px] font-bold text-[var(--color-text)]">Smart Alerts</h3>
          <button
            onClick={fetchData}
            className="ml-auto text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1 rounded"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
        <div className="text-[12px] text-[var(--color-text-muted)]">
          No hay alertas activas. Todo bajo control.
        </div>
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Zap size={16} className="text-[var(--color-warning)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Smart Alerts</h3>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--color-warning)]/15 text-[var(--color-warning)] font-semibold">
          {visibleAlerts.length}
        </span>
        <button
          onClick={fetchData}
          className="ml-auto text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1 rounded"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="space-y-2">
        {visibleAlerts.map((alert) => {
          const Icon = ALERT_ICONS[alert.type] || AlertTriangle;
          const color = getUrgencyColor(alert.urgency);

          return (
            <div
              key={alert.id}
              className="rounded-lg border border-[var(--color-border)] p-2.5 space-y-1.5"
              style={{ borderLeftColor: color, borderLeftWidth: 3 }}
            >
              <div className="flex items-start gap-2">
                <Icon size={14} style={{ color }} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-semibold text-[var(--color-text)]">
                    {alert.title}
                  </div>
                  <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                    {alert.detail}
                  </div>
                </div>
                <button
                  onClick={() => handleDismiss(alert.id)}
                  className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-0.5 rounded flex-shrink-0"
                >
                  <X size={12} />
                </button>
              </div>

              <div className="flex items-center gap-2">
                <div
                  className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                  style={{ color, backgroundColor: `${color}15` }}
                >
                  {getUrgencyLabel(alert.urgency)}
                </div>
                {/* Urgency bar */}
                <div className="flex-1 h-1 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${alert.urgency}%`, backgroundColor: color }}
                  />
                </div>
                {alert.action && onAction && (
                  <button
                    onClick={() => onAction(alert.action!)}
                    className="text-[10px] font-semibold text-[var(--color-primary)] hover:underline flex items-center gap-1"
                  >
                    <Search size={10} />
                    Ver
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
