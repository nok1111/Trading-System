import { useEffect, useState } from "react";
import { RegimeBanner } from "../components/intelligence/RegimeBanner";
import { FearGreedGauge } from "../components/intelligence/FearGreedGauge";
import { DominanceChart } from "../components/intelligence/DominanceChart";
import { DailyReportCard } from "../components/intelligence/DailyReportCard";
import { SignalList } from "../components/intelligence/SignalList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { SinceLastVisit } from "../components/dashboard/SinceLastVisit";
import { TodayPriorities } from "../components/dashboard/TodayPriorities";
import { AIActivityTimeline } from "../components/dashboard/AIActivityTimeline";
import {
  getMarketOverview,
  getFearGreed,
  getDominance,
  getDailyReport,
  getSignals,
  getSinceLastVisit,
  getTodayPriorities,
  getAIActivity,
} from "../lib/intelligenceApi";
import type {
  MarketOverview,
  FearGreedData,
  DominanceData,
  DailyReport,
  IntelligenceSignal,
  SinceLastVisitData,
  TodayPrioritiesData,
  AIActivityData,
} from "../lib/intelligenceTypes";

export function DashboardPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);
  const [dominance, setDominance] = useState<DominanceData | null>(null);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [signals, setSignals] = useState<IntelligenceSignal[]>([]);
  const [sinceLastVisit, setSinceLastVisit] = useState<SinceLastVisitData | null>(null);
  const [priorities, setPriorities] = useState<TodayPrioritiesData | null>(null);
  const [activity, setActivity] = useState<AIActivityData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [ov, fg, dom, rep, sig, slv, pri, act] = await Promise.all([
        getMarketOverview(),
        getFearGreed(),
        getDominance(),
        getDailyReport(),
        getSignals(3),
        getSinceLastVisit(),
        getTodayPriorities(),
        getAIActivity(),
      ]);
      if (!alive) return;
      setOverview(ov);
      setFearGreed(fg);
      setDominance(dom);
      setReport(rep);
      setSignals(sig);
      setSinceLastVisit(slv);
      setPriorities(pri);
      setActivity(act);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  return (
    <div className="p-5 space-y-5 max-w-[1200px] mx-auto">
      <SinceLastVisit data={sinceLastVisit} loading={loading} />

      <TodayPriorities data={priorities} loading={loading} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AIActivityTimeline data={activity} loading={loading} />
        <div className="space-y-4">
          <RegimeBanner overview={overview} loading={loading} />
          <div className="grid grid-cols-2 gap-3">
            <div className="panel p-3">
              <h3 className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">Fear & Greed</h3>
              <FearGreedGauge data={fearGreed} loading={loading} />
            </div>
            <div className="panel p-3">
              <h3 className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">BTC Dominance</h3>
              <DominanceChart data={dominance} loading={loading} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Señales Activas</h3>
          {loading ? <LoadingSkeleton lines={3} /> : <SignalList signals={signals} />}
        </div>
        <DailyReportCard report={report} loading={loading} />
      </div>
    </div>
  );
}
