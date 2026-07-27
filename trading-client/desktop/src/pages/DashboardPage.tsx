import { useEffect, useState } from "react";
import { RegimeBanner } from "../components/intelligence/RegimeBanner";
import { FearGreedGauge } from "../components/intelligence/FearGreedGauge";
import { DominanceChart } from "../components/intelligence/DominanceChart";
import { DailyReportCard } from "../components/intelligence/DailyReportCard";
import { SignalList } from "../components/intelligence/SignalList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import {
  getMarketOverview,
  getFearGreed,
  getDominance,
  getDailyReport,
  getSignals,
} from "../lib/intelligenceApi";
import type {
  MarketOverview,
  FearGreedData,
  DominanceData,
  DailyReport,
  IntelligenceSignal,
} from "../lib/intelligenceTypes";

export function DashboardPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);
  const [dominance, setDominance] = useState<DominanceData | null>(null);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [signals, setSignals] = useState<IntelligenceSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [ov, fg, dom, rep, sig] = await Promise.all([
        getMarketOverview(),
        getFearGreed(),
        getDominance(),
        getDailyReport(),
        getSignals(3),
      ]);
      if (!alive) return;
      setOverview(ov);
      setFearGreed(fg);
      setDominance(dom);
      setReport(rep);
      setSignals(sig);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  return (
    <div className="p-5 space-y-4 max-w-[1200px] mx-auto">
      <RegimeBanner overview={overview} loading={loading} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Fear & Greed</h3>
          <FearGreedGauge data={fearGreed} loading={loading} />
        </div>
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">BTC Dominance</h3>
          <DominanceChart data={dominance} loading={loading} />
        </div>
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Señales Activas</h3>
          {loading ? <LoadingSkeleton lines={3} /> : <SignalList signals={signals} />}
        </div>
      </div>

      <DailyReportCard report={report} loading={loading} />
    </div>
  );
}
