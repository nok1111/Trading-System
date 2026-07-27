import { useEffect, useState } from "react";
import { AlertList } from "../components/intelligence/AlertList";
import { PendingList } from "../components/intelligence/PendingList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getAlerts, getPendingNotifications, markNotificationRead } from "../lib/intelligenceApi";
import type { IntelligenceAlert, PendingNotification } from "../lib/intelligenceTypes";
import { useAuthContext } from "../context/AuthContext";

export function AlertsPage() {
  const { user } = useAuthContext();
  const [alerts, setAlerts] = useState<IntelligenceAlert[]>([]);
  const [pending, setPending] = useState<PendingNotification[]>([]);
  const [loading, setLoading] = useState(true);

  const userHash = user?.email ? btoa(user.email).slice(0, 16) : "anon";

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [a, p] = await Promise.all([
        getAlerts(20),
        getPendingNotifications(userHash),
      ]);
      if (!alive) return;
      setAlerts(a);
      setPending(p);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, [userHash]);

  const handleMarkRead = async (id: number) => {
    await markNotificationRead(id, userHash);
    setPending((prev) => prev.map((n) => n.id === id ? { ...n, read: true } : n));
  };

  return (
    <div className="p-5 space-y-4 max-w-[700px] mx-auto">
      <div>
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Notificaciones Pendientes</h3>
        {loading ? <LoadingSkeleton lines={3} /> : <PendingList notifications={pending} onMarkRead={handleMarkRead} />}
      </div>
      <div>
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Alertas</h3>
        {loading ? <LoadingSkeleton lines={3} /> : <AlertList alerts={alerts} />}
      </div>
    </div>
  );
}
