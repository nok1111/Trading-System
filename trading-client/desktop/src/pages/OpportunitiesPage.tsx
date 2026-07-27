import { useEffect, useState } from "react";
import { SignalList } from "../components/intelligence/SignalList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getSignals } from "../lib/intelligenceApi";
import type { IntelligenceSignal } from "../lib/intelligenceTypes";

export function OpportunitiesPage() {
  const [signals, setSignals] = useState<IntelligenceSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const s = await getSignals(20);
      if (!alive) return;
      setSignals(s);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  return (
    <div className="p-5 max-w-[800px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-4">Señales Activas</h2>
      {loading ? <LoadingSkeleton lines={6} /> : <SignalList signals={signals} />}
    </div>
  );
}
