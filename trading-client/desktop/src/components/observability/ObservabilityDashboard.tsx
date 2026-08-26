import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Clock,
  Database,
  Zap,
  Server,
  Shield,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import {
  getHealth,
  getAuditSummary,
  getAuditLogs,
  type HealthCheck,
  type AuditSummary,
  type AuditLog,
} from "../../lib/observabilityApi";

const LEVEL_COLORS: Record<string, string> = {
  info: "var(--color-text-muted)",
  warning: "var(--color-warning)",
  error: "var(--color-danger)",
  critical: "var(--color-danger)",
};

const SOURCE_ICONS: Record<string, typeof Activity> = {
  auth: Shield,
  broker: Server,
  trading: TrendingUp,
  security: Shield,
  settings: Activity,
  copilot: Zap,
  api: Activity,
};

export function ObservabilityDashboard() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterLevel, setFilterLevel] = useState<string | undefined>(undefined);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, s, l] = await Promise.all([
        getHealth(),
        getAuditSummary(24),
        getAuditLogs({ limit: 50, level: filterLevel }),
      ]);
      setHealth(h);
      setSummary(s);
      setLogs(l.logs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading observability data");
    } finally {
      setLoading(false);
    }
  }, [filterLevel]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  const formatUptime = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600) return `${(seconds / 60).toFixed(0)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  if (loading && !health) {
    return (
      <div className="p-5 max-w-[1400px] mx-auto">
        <div className="panel p-8 flex items-center justify-center text-[var(--color-text-muted)] text-[13px]">
          <Activity size={16} className="animate-pulse mr-2" />
          Cargando observabilidad...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-5 max-w-[1400px] mx-auto">
        <div className="panel p-4 border-l-4" style={{ borderLeftColor: "var(--color-danger)" }}>
          <div className="flex items-center gap-2 text-[var(--color-danger)]">
            <AlertCircle size={16} />
            <span className="text-[13px] font-semibold">Error: {error}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={20} className="text-[var(--color-primary)]" />
          <h1 className="text-[18px] font-bold text-[var(--color-text)]">Observabilidad</h1>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-surface-2)] hover:bg-[var(--color-surface-hover)] text-[12px] font-semibold text-[var(--color-text)]"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Actualizar
        </button>
      </div>

      {/* Health Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Database */}
        <HealthCard
          icon={Database}
          label="Database"
          status={health?.checks.database.status || "unknown"}
          detail={health?.checks.database.latency_ms != null ? `${health.checks.database.latency_ms}ms` : undefined}
        />
        {/* Cache */}
        <HealthCard
          icon={Zap}
          label="Cache"
          status={health?.checks.cache.status || "unknown"}
          detail={health?.checks.cache.size != null ? `${health.checks.cache.size} items` : undefined}
        />
        {/* Rate Limiter */}
        <HealthCard
          icon={Shield}
          label="Rate Limiter"
          status={health?.checks.rate_limiter.status || "unknown"}
          detail={health?.checks.rate_limiter.tracked_keys != null ? `${health.checks.rate_limiter.tracked_keys} keys` : undefined}
        />
        {/* Brokers */}
        <HealthCard
          icon={Server}
          label="Brokers"
          status={health?.checks.brokers.status || "unknown"}
          detail={health?.checks.brokers.available_brokers != null ? `${health.checks.brokers.available_brokers} disponibles` : undefined}
        />
      </div>

      {/* System Info */}
      {health && (
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <Server size={16} className="text-[var(--color-primary)]" />
            <h2 className="text-[14px] font-bold text-[var(--color-text)]">System Info</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <InfoItem icon={CheckCircle} label="Status" value={health.status} color={health.status === "healthy" ? "var(--color-success)" : "var(--color-danger)"} />
            <InfoItem icon={Clock} label="Uptime" value={formatUptime(health.uptime_seconds)} />
            <InfoItem icon={Activity} label="Version" value={health.version} />
            <InfoItem icon={TrendingUp} label="Total Events (24h)" value={String(summary?.total_events || 0)} />
          </div>
        </div>
      )}

      {/* Audit Summary */}
      {summary && (
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield size={16} className="text-[var(--color-primary)]" />
            <h2 className="text-[14px] font-bold text-[var(--color-text)]">Audit Summary (24h)</h2>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <LevelBar label="Info" count={summary.by_level.info} color="var(--color-text-muted)" />
            <LevelBar label="Warning" count={summary.by_level.warning} color="var(--color-warning)" />
            <LevelBar label="Error" count={summary.by_level.error} color="var(--color-danger)" />
            <LevelBar label="Critical" count={summary.by_level.critical} color="var(--color-danger)" />
          </div>
        </div>
      )}

      {/* Audit Logs */}
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Clock size={16} className="text-[var(--color-primary)]" />
          <h2 className="text-[14px] font-bold text-[var(--color-text)]">Audit Logs</h2>
          {/* Level filter */}
          <div className="ml-auto flex items-center gap-1">
            {["all", "info", "warning", "error", "critical"].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setFilterLevel(lvl === "all" ? undefined : lvl)}
                className={`px-2 py-1 rounded text-[10px] font-semibold transition-colors ${
                  (filterLevel || "all") === lvl
                    ? "bg-[var(--color-primary)] text-white"
                    : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        {logs.length === 0 ? (
          <div className="text-center py-8 text-[12px] text-[var(--color-text-muted)]">
            No hay eventos de audit en este periodo.
          </div>
        ) : (
          <div className="space-y-1 max-h-[400px] overflow-y-auto">
            {logs.map((log) => {
              const Icon = SOURCE_ICONS[log.source] || Activity;
              const color = LEVEL_COLORS[log.level] || "var(--color-text-muted)";
              return (
                <div
                  key={log.id}
                  className="flex items-start gap-2.5 px-2.5 py-2 rounded-lg hover:bg-[var(--color-surface-2)] transition-colors"
                  style={{ borderLeft: `2px solid ${color}`, paddingLeft: "10px" }}
                >
                  <Icon size={14} style={{ color }} className="mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-semibold text-[var(--color-text)] truncate">
                        {log.message}
                      </span>
                      <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded" style={{ color, backgroundColor: `${color}15` }}>
                        {log.level}
                      </span>
                    </div>
                    <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                      {formatTime(log.timestamp)} · {log.source}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function HealthCard({ icon: Icon, label, status, detail }: {
  icon: typeof Activity;
  label: string;
  status: string;
  detail?: string;
}) {
  const isHealthy = status === "healthy";
  const color = isHealthy ? "var(--color-success)" : "var(--color-danger)";

  return (
    <div className="panel p-3" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} style={{ color }} />
        <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">{label}</span>
      </div>
      <div className="text-[14px] font-bold" style={{ color }}>
        {isHealthy ? "Healthy" : "Unhealthy"}
      </div>
      {detail && <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">{detail}</div>}
    </div>
  );
}

function InfoItem({ icon: Icon, label, value, color }: {
  icon: typeof Activity;
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={14} className="text-[var(--color-text-muted)]" />
      <div>
        <div className="text-[10px] text-[var(--color-text-muted)] uppercase font-bold">{label}</div>
        <div className="text-[13px] font-semibold" style={{ color: color || "var(--color-text)" }}>
          {value}
        </div>
      </div>
    </div>
  );
}

function LevelBar({ label, count, color }: {
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div className="rounded-lg p-2.5" style={{ backgroundColor: `${color}10` }}>
      <div className="text-[10px] font-bold uppercase" style={{ color }}>{label}</div>
      <div className="text-[20px] font-bold" style={{ color }}>{count}</div>
    </div>
  );
}
