import { useEffect, useState, useCallback } from "react";
import { Bell, Check, CheckCheck, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { fmtDate } from "../../lib/utils";
import type { PendingNotification } from "../../lib/intelligenceTypes";
import {
  getNotifications,
  getUnreadNotificationCount,
  markNotificationRead,
  markAllNotificationsRead,
} from "../../lib/intelligenceApi";

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
};

interface NotificationDropdownProps {
  open: boolean;
  onClose: () => void;
  onNavigate?: (page: string) => void;
}

export function NotificationDropdown({ open, onClose, onNavigate }: NotificationDropdownProps) {
  const [notifications, setNotifications] = useState<PendingNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    const [notifs, count] = await Promise.all([
      getNotifications(filter === "unread", 30),
      getUnreadNotificationCount(),
    ]);
    setNotifications(notifs);
    setUnreadCount(count);
    setLoading(false);
  }, [filter]);

  useEffect(() => {
    if (open) {
      loadNotifications();
    }
  }, [open, loadNotifications]);

  useEffect(() => {
    if (!open) return;
    const id = setInterval(loadNotifications, 15000);
    return () => clearInterval(id);
  }, [open, loadNotifications]);

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
    if (n.action_url && onNavigate) {
      onNavigate(n.action_url);
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div className="absolute z-30 right-0 top-11 w-[360px] panel overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <Bell size={14} className="text-[var(--color-primary)]" />
          <span className="text-[12px] font-bold text-[var(--color-text)]">Notificaciones</span>
          {unreadCount > 0 && (
            <span className="text-[10px] font-bold text-white bg-[var(--color-danger)] px-1.5 h-4 rounded-full flex items-center justify-center">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setFilter((f) => (f === "all" ? "unread" : "all"))}
            className="text-[10px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] px-1.5 py-0.5 rounded"
          >
            {filter === "all" ? "Solo no leídas" : "Ver todas"}
          </button>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="flex items-center gap-1 text-[10px] font-bold text-[var(--color-success)] hover:opacity-80 px-1.5 py-0.5 rounded"
              title="Marcar todas como leídas"
            >
              <CheckCheck size={11} />
              Leer todas
            </button>
          )}
          <button
            onClick={onClose}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="max-h-[400px] overflow-y-auto divide-y divide-[var(--color-border)]">
        {loading ? (
          <div className="px-3 py-8 text-center text-[12px] text-[var(--color-text-muted)]">
            Cargando...
          </div>
        ) : notifications.length === 0 ? (
          <div className="px-3 py-8 text-center text-[12px] text-[var(--color-text-muted)]">
            <Bell size={20} className="mx-auto mb-2 opacity-30" />
            Sin notificaciones
          </div>
        ) : (
          notifications.map((n) => {
            const sev = SEVERITY_STYLES[n.severity] || SEVERITY_STYLES.info;
            const typeIcon = TYPE_ICONS[n.type] || "🔔";
            return (
              <button
                key={n.id}
                onClick={() => handleClick(n)}
                className={cn(
                  "w-full flex items-start gap-2.5 px-3 py-2.5 text-left hover:bg-[var(--color-surface-hover)] transition-colors",
                  !n.read && "bg-[var(--color-primary)]/5"
                )}
              >
                {/* Icon */}
                <div className="flex-shrink-0 mt-0.5">
                  <div className={cn("w-7 h-7 rounded-full flex items-center justify-center text-[12px]", sev.bg)}>
                    <span className="text-[13px]">{typeIcon}</span>
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={cn("text-[12px] font-bold truncate", !n.read ? "text-[var(--color-text)]" : "text-[var(--color-text-muted)]")}>
                      {n.title}
                    </span>
                    {!n.read && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] flex-shrink-0" />
                    )}
                  </div>
                  {n.message && (
                    <p className="text-[11px] text-[var(--color-text-muted)] line-clamp-2 leading-relaxed">
                      {n.message}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-[var(--color-text-muted)]">{fmtDate(n.timestamp)}</span>
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
                    <Check size={13} />
                  </button>
                )}
              </button>
            );
          })
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="px-3 py-2 border-t border-[var(--color-border)] flex items-center justify-between">
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {notifications.length} notificación{notifications.length !== 1 ? "es" : ""}
          </span>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="flex items-center gap-1 text-[10px] font-bold text-[var(--color-primary)] hover:opacity-80"
            >
              <CheckCheck size={11} />
              Marcar todas leídas
            </button>
          )}
        </div>
      )}
    </div>
  );
}
