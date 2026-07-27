import { Bell, Check } from "lucide-react";
import { cn } from "../../lib/utils";
import { EmptyState } from "../common/EmptyState";
import type { PendingNotification } from "../../lib/intelligenceTypes";
import { fmtDate } from "../../lib/utils";

interface PendingListProps {
  notifications: PendingNotification[];
  onMarkRead?: (id: number) => void;
  className?: string;
}

export function PendingList({ notifications, onMarkRead, className }: PendingListProps) {
  if (notifications.length === 0) {
    return (
      <EmptyState
        title="Sin notificaciones"
        description="No hay notificaciones pendientes."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {notifications.map((n) => (
        <div
          key={n.id}
          className={cn(
            "flex items-start gap-3 rounded-[10px] bg-[var(--color-surface)] border p-3",
            n.read ? "border-[var(--color-border)] opacity-60" : "border-[var(--color-primary)]/30"
          )}
        >
          <Bell size={15} className={cn("flex-shrink-0 mt-0.5", n.read ? "text-[var(--color-text-muted)]" : "text-[var(--color-primary)]")} />
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-bold text-[var(--color-text)]">{n.title}</p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{n.message}</p>
            <p className="text-[10px] text-[var(--color-text-muted)] mt-1">{fmtDate(n.timestamp)}</p>
          </div>
          {!n.read && onMarkRead && (
            <button
              onClick={() => onMarkRead(n.id)}
              className="text-[var(--color-text-muted)] hover:text-[var(--color-success)] flex-shrink-0"
              title="Marcar como leída"
            >
              <Check size={15} />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
