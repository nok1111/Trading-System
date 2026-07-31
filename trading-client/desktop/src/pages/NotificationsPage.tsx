import { useEffect, useState, useCallback } from "react";
import { Bell, Check, CheckCheck, Filter } from "lucide-react";
import { cn, fmtDate } from "../lib/utils";
import type { PendingNotification } from "../lib/intelligenceTypes";
import {
  getNotifications,
  getUnreadNotificationCount,
  markNotificationRead,
  markAllNotificationsRead,
} from "../lib/intelligenceApi";

const SEVERITY_STYLES: Record<string, { bg: string; text: string }> = {
  info: { bg: "bg-[var(--color-primary)]/10", text: "text-[var(--color-primary)]" },
  warning: { bg: "bg-[var(--color-warning)]/10", text: "text-[var(--color-warning)]" },
  critical: { bg: "bg-[var(--color-danger)]/10", text: "text-[var(--color-danger)]" },
};

const TYPE_ICONS: Record<string, string> = {
  trade_executed: "🟢",
  stop_loss_hit: "🛑",
  take_profit_hit: "🎯",
  trailing_stop_update: "📈",
  news_high_impact: "📰",
  risk_warning: "⚠️",
  ai_decision: "🤖",
  portfolio_change: "📊",
  system_event: "⚙️",
  consensus_change: "🔄",
  signal_alert: "📡",
  technical_exit: "📉",
  position_analysis_started: "🔬",
  position_analysis_completed: "✅",
  position_analysis_error: "❌",
};

const TYPE_LABELS: Record<string, string> = {
  trade_executed: "Trades",
  stop_loss_hit: "Stop Loss",
  take_profit_hit: "Take Profit",
  trailing_stop_update: "Trailing Stop",
  technical_exit: "Salida Técnica",
  news_high_impact: "Noticias",
  risk_warning: "Riesgos",
  ai_decision: "IA",
  portfolio_change: "Portfolio",
  system_event: "Sistema",
  consensus_change: "Consenso",
  signal_alert: "Señales",
  position_analysis_started: "Análisis IA",
  position_analysis_completed: "Análisis IA",
  position_analysis_error: "Análisis IA",
};

const TYPE_FILTERS = [
  { value: "all", label: "Todas" },
  { value: "unread", label: "No leídas" },
  { value: "trade_executed", label: "Trades" },
  { value: "ai", label: "IA" },
  { value: "risk", label: "Riesgos" },
  { value: "system", label: "Sistema" },
];

const AI_TYPES = ["ai_decision", "position_analysis_started", "position_analysis_completed", "position_analysis_error", "consensus_change", "signal_alert"];
const RISK_TYPES = ["risk_warning", "stop_loss_hit", "take_profit_hit", "trailing_stop_update", "technical_exit"];
const SYSTEM_TYPES = ["system_event", "portfolio_change"];

interface NotificationsPageProps {
  onNavigate?: (page: string) => void;
}

export function NotificationsPage({ onNavigate }: NotificationsPageProps) {
  const [notifications, setNotifications] = useState<PendingNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [limit, setLimit] = useState(50);

  const loadNotifications = useCallback(async () => {
    const unreadOnly = filter === "unread";
    const notifs = await getNotifications(unreadOnly, limit);
    let filtered = notifs;

    if (filter === "ai") {
      filtered = notifs.filter((n) => AI_TYPES.includes(n.type));
    } else if (filter === "risk") {
      filtered = notifs.filter((n) => RISK_TYPES.includes(n.type));
    } else if (filter === "system") {
      filtered = notifs.filter((n) => SYSTEM_TYPES.includes(n.type));
    } else if (filter === "trade_executed") {
      filtered = notifs.filter((n) => n.type === "trade_executed");
    }

    setNotifications(filtered);
    const count = await getUnreadNotificationCount();
    setUnreadCount(count);
    setLoading(false);
  }, [filter, limit]);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  useEffect(() => {
    const id = setInterval(loadNotifications, 30000);
    return () => clearInterval(id);
  }, [loadNotifications]);

  const handleMarkRead = async (id: number) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    setUnreadCount((c) => Math.max(0, c - 1));
    await markNotificationRead(id);
  };

  const handleMarkAllRead = async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);
    await markAllNotificationsRead();
  };

  const handleClick = (n: PendingNotification) => {
    if (!n.read) handleMarkRead(n.id);
    const target = n.action_url || "/alerts";
    if (onNavigate) {
      onNavigate(target.replace("/", ""));
    }
  };

  const handleLoadMore = () => {
    setLimit((l) => l + 50);
  };

  return (
    <div className="p-5 space-y-4 max-w-[900px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell size={18} className="text-[var(--color-primary)]" />
          <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Notificaciones</h2>
          {unreadCount > 0 && (
            <span className="text-[10px] font-bold text-white bg-[var(--color-danger)] px-1.5 h-5 rounded-full flex items-center justify-center">
              {unreadCount}
            </span>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllRead}
            className="flex items-center gap-1.5 text-[11px] font-bold text-[var(--color-success)] hover:opacity-80 px-2.5 h-8 rounded-[8px] bg-[var(--color-success)]/10 transition-opacity"
          >
            <CheckCheck size={13} />
            Marcar todas leídas
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter size={13} className="text-[var(--color-text-muted)]" />
        {TYPE_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => { setFilter(f.value); setLoading(true); }}
            className={cn(
              "text-[11px] font-bold px-2.5 h-7 rounded-[6px] transition-colors",
              filter === f.value
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-2">
        {loading ? (
          <div className="panel p-8 text-center text-[13px] text-[var(--color-text-muted)]">
            Cargando...
          </div>
        ) : notifications.length === 0 ? (
          <div className="panel p-8 text-center">
            <Bell size={28} className="mx-auto mb-3 opacity-20" />
            <p className="text-[13px] text-[var(--color-text-muted)]">Sin notificaciones</p>
          </div>
        ) : (
          <>
            {notifications.map((n) => {
              const sev = SEVERITY_STYLES[n.severity] || SEVERITY_STYLES.info;
              const typeIcon = TYPE_ICONS[n.type] || "🔔";
              const typeLabel = TYPE_LABELS[n.type] || n.type;
              return (
                <div
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={cn(
                    "flex items-start gap-3 rounded-[10px] border p-3 cursor-pointer transition-colors hover:bg-[var(--color-surface-hover)]",
                    !n.read
                      ? "bg-[var(--color-primary)]/5 border-[var(--color-primary)]/30"
                      : "bg-[var(--color-surface)] border-[var(--color-border)]"
                  )}
                >
                  {/* Icon */}
                  <div className="flex-shrink-0 mt-0.5">
                    <div className={cn("w-8 h-8 rounded-full flex items-center justify-center text-[13px]", sev.bg)}>
                      <span className="text-[14px]">{typeIcon}</span>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={cn("text-[13px] font-bold truncate", !n.read ? "text-[var(--color-text)]" : "text-[var(--color-text-muted)]")}>
                        {n.title}
                      </span>
                      {!n.read && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] flex-shrink-0" />
                      )}
                    </div>
                    {n.message && (
                      <p className="text-[12px] text-[var(--color-text-muted)] line-clamp-2 leading-relaxed">
                        {n.message}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-[var(--color-text-muted)]">{fmtDate(n.timestamp)}</span>
                      <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase px-1.5 h-4 rounded bg-[var(--color-surface-2)] flex items-center">
                        {typeLabel}
                      </span>
                      {n.asset && (
                        <span className="text-[10px] font-bold text-[var(--color-accent)]">{n.asset}</span>
                      )}
                    </div>
                  </div>

                  {/* Mark read */}
                  {!n.read && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMarkRead(n.id);
                      }}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-success)] flex-shrink-0 mt-1"
                      title="Marcar como leída"
                    >
                      <Check size={15} />
                    </button>
                  )}
                </div>
              );
            })}

            {/* Load more */}
            {notifications.length >= limit && (
              <div className="text-center py-3">
                <button
                  onClick={handleLoadMore}
                  className="text-[12px] font-bold text-[var(--color-primary)] hover:opacity-80 px-4 h-8 rounded-[8px] bg-[var(--color-surface-2)] transition-opacity"
                >
                  Cargar más
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
