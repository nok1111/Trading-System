import { useEffect, useState } from "react";
import { ReportList } from "../components/intelligence/ReportList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { getReports } from "../lib/intelligenceApi";
import type { IntelligenceReport } from "../lib/intelligenceTypes";

export function ReportsPage() {
  const [reports, setReports] = useState<IntelligenceReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const r = await getReports("BTC");
      if (!alive) return;
      setReports(r);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  return (
    <div className="p-5 max-w-[700px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-4">Reportes</h2>
      {loading ? <LoadingSkeleton lines={4} /> : <ReportList reports={reports} />}
    </div>
  );
}
