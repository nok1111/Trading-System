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
import { OnboardingModal } from "../components/dashboard/OnboardingModal";
import {
  getMarketOverview,
  getFearGreed,
  getDominance,
  getDailyReport,
  getSignals,
  getSinceLastVisit,
  getTodayPriorities,
  getAIActivity,
  getUserProfile,
  type UserProfileData,
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
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [userProfile, setUserProfile] = useState<UserProfileData | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [profileResult, ...rest] = await Promise.allSettled([
        getUserProfile(),
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

      const profile = profileResult.status === "fulfilled" ? profileResult.value : null;
      setUserProfile(profile);
      if (!profile || !profile.onboarding_completed) {
        setShowOnboarding(true);
      }

      const get = (i: number) => rest[i].status === "fulfilled" ? rest[i].value : null;
      setOverview(get(0) as MarketOverview | null);
      setFearGreed(get(1) as FearGreedData | null);
      setDominance(get(2) as DominanceData | null);
      setReport(get(3) as DailyReport | null);
      setSignals(get(4) as IntelligenceSignal[] | null ?? []);
      setSinceLastVisit(get(5) as SinceLastVisitData | null);
      setPriorities(get(6) as TodayPrioritiesData | null);
      setActivity(get(7) as AIActivityData | null);
      setLoading(false);
    };
    load();
    return () => { alive = false; };
  }, []);

  if (showOnboarding) {
    return (
      <OnboardingModal
        onComplete={(profile) => {
          setUserProfile(profile);
          setShowOnboarding(false);
        }}
      />
    );
  }

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
