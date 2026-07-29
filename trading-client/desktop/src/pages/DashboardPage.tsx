import { useEffect, useState } from "react";
import { RegimeBanner } from "../components/intelligence/RegimeBanner";
import { DominanceChart } from "../components/intelligence/DominanceChart";
import { DailyReportCard } from "../components/intelligence/DailyReportCard";
import { SignalList } from "../components/intelligence/SignalList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { WelcomePortal } from "../components/dashboard/WelcomePortal";
import { TodayPriorities } from "../components/dashboard/TodayPriorities";
import { AIActivityTimeline } from "../components/dashboard/AIActivityTimeline";
import { OnboardingModal } from "../components/dashboard/OnboardingModal";
import { useAuthContext } from "../context/AuthContext";
import {
  getMarketOverview,
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
  DominanceData,
  DailyReport,
  IntelligenceSignal,
  SinceLastVisitData,
  TodayPrioritiesData,
  AIActivityData,
} from "../lib/intelligenceTypes";

export function DashboardPage() {
  const { user } = useAuthContext();
  const [overview, setOverview] = useState<MarketOverview | null>(null);
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
      setDominance(get(1) as DominanceData | null);
      setReport(get(2) as DailyReport | null);
      setSignals(get(3) as IntelligenceSignal[] | null ?? []);
      setSinceLastVisit(get(4) as SinceLastVisitData | null);
      setPriorities(get(5) as TodayPrioritiesData | null);
      setActivity(get(6) as AIActivityData | null);
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
    <div className="p-5 space-y-4 max-w-[900px] mx-auto">
      {/* Conversational welcome — AI greets you like a friend */}
      <WelcomePortal data={sinceLastVisit} profile={userProfile} loading={loading} username={user?.username} />

      {/* Market pulse — subtle, not overwhelming */}
      <div className="grid grid-cols-2 gap-3">
        <div className="panel p-3">
          <h3 className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">BTC Dominance</h3>
          <DominanceChart data={dominance} loading={loading} />
        </div>
        <div className="panel p-3">
          <h3 className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">Mercado</h3>
          <RegimeBanner overview={overview} loading={loading} />
        </div>
      </div>

      {/* What to review today — friendly priorities */}
      <TodayPriorities data={priorities} loading={loading} />

      {/* AI activity + signals — side by side, compact */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AIActivityTimeline data={activity} loading={loading} />
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Señales que están activas ahora</h3>
          {loading ? <LoadingSkeleton lines={3} /> : <SignalList signals={signals} />}
        </div>
      </div>

      {/* Daily report — at the bottom, optional read */}
      <DailyReportCard report={report} loading={loading} />
    </div>
  );
}
