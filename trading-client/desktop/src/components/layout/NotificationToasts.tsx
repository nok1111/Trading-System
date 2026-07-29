import { useEffect, useRef, useState, useCallback } from "react";
import { X, AlertTriangle, Info } from "lucide-react";
import { cn } from "../../lib/utils";
import { getNotifications } from "../../lib/intelligenceApi";
import type { PendingNotification } from "../../lib/intelligenceTypes";

const SEVERITY_CONFIG: Record<string, { bg: string; border: string; icon: typeof Info }> = {
  info: { bg: "bg-[var(--color-primary)]/10", border: "border-[var(--color-primary)]/30", icon: Info },
  warning: { bg: "bg-[var(--color-warning)]/10", border: "border-[var(--color-warning)]/30", icon: AlertTriangle },
  critical: { bg: "bg-[var(--color-danger)]/10", border: "border-[var(--color-danger)]/30", icon: AlertTriangle },
};

interface ToastItem {
  id: number;
  notif: PendingNotification;
  closing: boolean;
}

export function NotificationToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const lastNotifIdRef = useRef<number>(0);
  const seenIdsRef = useRef<Set<number>>(new Set());

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, closing: true } : t)));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 300);
  }, []);

  useEffect(() => {
    let alive = true;

    const poll = async () => {
      const notifs = await getNotifications(true, 5);
      if (!alive) return;

      for (const n of notifs) {
        if (seenIdsRef.current.has(n.id)) continue;
        seenIdsRef.current.add(n.id);
        if (n.id > lastNotifIdRef.current) {
          lastNotifIdRef.current = n.id;
          setToasts((prev) => [...prev, { id: n.id, notif: n, closing: false }]);
          setTimeout(() => removeToast(n.id), 8000);
        }
      }
    };

    poll();
    const interval = setInterval(poll, 10000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [removeToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-[360px]">
      {toasts.map((toast) => {
        const n = toast.notif;
        const config = SEVERITY_CONFIG[n.severity] || SEVERITY_CONFIG.info;
        const Icon = config.icon;
        return (
          <div
            key={toast.id}
            className={cn(
              "panel p-3 flex items-start gap-2.5 shadow-lg transition-all duration-300",
              config.bg,
              config.border,
              "border",
              toast.closing ? "opacity-0 translate-x-4" : "opacity-100 translate-x-0"
            )}
          >
            <div className={cn("flex-shrink-0 mt-0.5", config.border.replace("border", "text"))}>
              <Icon size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-bold text-[var(--color-text)]">{n.title}</p>
              {n.message && (
                <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5 line-clamp-2">{n.message}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] flex-shrink-0"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
