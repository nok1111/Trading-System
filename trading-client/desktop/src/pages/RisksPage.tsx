import { useEffect, useState } from "react";
import { AlertList } from "../components/intelligence/AlertList";
import { CrashRiskGauge } from "../components/intelligence/CrashRiskGauge";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getAlerts } from "../lib/intelligenceApi";
import type { IntelligenceAlert } from "../lib/intelligenceTypes";

export function RisksPage() {
  const [alerts, setAlerts] = useState<IntelligenceAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const a = await getAlerts(20);
      if (!alive) return;
      setAlerts(a);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  const crashRisk = alerts.find((a) => a.crashRisk != null)?.crashRisk ?? null;

  return (
    <div className="p-5 space-y-4 max-w-[800px] mx-auto">
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Crash Risk</h3>
        <CrashRiskGauge crashRisk={crashRisk} loading={loading} />
      </div>
      <div>
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Alertas de Riesgo</h3>
        {loading ? <LoadingSkeleton lines={4} /> : <AlertList alerts={alerts} />}
      </div>
    </div>
  );
}
