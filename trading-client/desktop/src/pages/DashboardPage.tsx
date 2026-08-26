import { useEffect, useState } from "react";
import { Wallet, TrendingUp, TrendingDown } from "lucide-react";
import { RegimeBanner } from "../components/intelligence/RegimeBanner";
import { DominanceChart } from "../components/intelligence/DominanceChart";
import { DailyReportCard } from "../components/intelligence/DailyReportCard";
import { SignalList } from "../components/intelligence/SignalList";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { WelcomePortal } from "../components/dashboard/WelcomePortal";
import { TodayPriorities } from "../components/dashboard/TodayPriorities";
import { AIActivityTimeline } from "../components/dashboard/AIActivityTimeline";
import { OnboardingModal } from "../components/dashboard/OnboardingModal";
import { AutoPilotWidget } from "../components/dashboard/AutoPilotWidget";
import { AlvoraSection } from "../components/dashboard/AlvoraSection";
import { Watchlist } from "../components/watchlist/Watchlist";
import { UnifiedPortfolioHero } from "../components/dashboard/UnifiedPortfolioHero";
import { PortfolioHeatmap } from "../components/dashboard/PortfolioHeatmap";
import { NetExposurePanel } from "../components/dashboard/NetExposurePanel";
import { CopilotSuggestionsPanel } from "../components/copilot/CopilotSuggestionsPanel";
import { SmartAlertsPanel } from "../components/copilot/SmartAlertsPanel";
import { useI18n } from "../i18n/I18nContext";
import { useAuthContext } from "../context/AuthContext";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
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

interface PortfolioSummary {
  error?: string;
  balance_usd: number;
  total_value: number;
  total_pnl: number;
  positions_count: number;
  positions: Array<{ symbol: string; unrealized_pnl: number; pnl_pct: number }>;
  distribution: Array<{ asset: string; usd: number; pct: number }>;
}

function fmtVol(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(2);
}

function PortfolioHero({ summary, loading }: { summary: PortfolioSummary | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="panel-hero p-6">
        <div className="h-8 w-48 bg-[var(--color-surface-2)] rounded animate-pulse mb-3" />
        <div className="h-6 w-32 bg-[var(--color-surface-2)] rounded animate-pulse" />
      </div>
    );
  }

  if (!summary || summary.total_value <= 0) {
    return null; // WelcomePortal will show instead
  }

  const pnl = summary.total_pnl || 0;
  const pnlPositive = pnl >= 0;
  const positions = summary.positions || [];
  const bestPerformer = positions.length > 0
    ? positions.reduce((best, p) => (p.unrealized_pnl > best.unrealized_pnl ? p : best))
    : null;
  const worstPerformer = positions.length > 0
    ? positions.reduce((worst, p) => (p.unrealized_pnl < worst.unrealized_pnl ? p : worst))
    : null;

  return (
    <div className="panel-hero p-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Col 1-2: Equity + P&L */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-1">
            <Wallet size={14} className="text-[var(--color-text-muted)]" />
            <span className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
              Total Equity
            </span>
          </div>
          <div className="num text-[32px] font-extrabold leading-none text-[var(--color-text)]">
            ${fmtVol(summary.total_value)}
          </div>
          <div className="flex items-center gap-3 mt-2">
            <span
              className={cn(
                "text-[15px] font-bold flex items-center gap-1",
                pnlPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}
            >
              {pnlPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              {pnlPositive ? "+" : ""}${fmtVol(Math.abs(pnl))}
            </span>
            <span className="text-[12px] text-[var(--color-text-muted)]">P&L total</span>
          </div>
          {/* Inline: positions count + best/worst performer */}
          <div className="flex items-center gap-4 mt-3 text-[12px]">
            <span className="text-[var(--color-text-muted)]">
              {summary.positions_count} {summary.positions_count === 1 ? "posición" : "posiciones"}
            </span>
            {bestPerformer && bestPerformer.unrealized_pnl > 0 && (
              <span className="text-[var(--color-success)] flex items-center gap-0.5">
                <TrendingUp size={11} />
                {bestPerformer.symbol.replace("USDT", "")}
              </span>
            )}
            {worstPerformer && worstPerformer.unrealized_pnl < 0 && (
              <span className="text-[var(--color-danger)] flex items-center gap-0.5">
                <TrendingDown size={11} />
                {worstPerformer.symbol.replace("USDT", "")}
              </span>
            )}
          </div>
        </div>
        {/* Col 3: Quick allocation breakdown */}
        <div className="flex flex-col justify-center">
          {summary.distribution && summary.distribution.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] uppercase font-bold text-[var(--color-text-muted)] tracking-wide">
                Allocation
              </span>
              {summary.distribution.slice(0, 5).map((d) => (
                <div key={d.asset} className="flex items-center gap-2">
                  <span className="text-[12px] font-bold text-[var(--color-text)] w-12 truncate">{d.asset}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[var(--color-primary)]"
                      style={{ width: `${Math.min(d.pct, 100)}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-[var(--color-text-muted)] w-10 text-right">{d.pct}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuthContext();
  const { t } = useI18n();
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
  const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [profileResult, portfolioResult, ...rest] = await Promise.allSettled([
        getUserProfile(),
        api<PortfolioSummary>("/api/ai-agent/portfolio-summary"),
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

      const portfolio = portfolioResult.status === "fulfilled" ? portfolioResult.value : null;
      setPortfolioSummary(portfolio && !portfolio.error ? portfolio : null);

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

  const hasPortfolio = portfolioSummary && portfolioSummary.total_value > 0;

  return (
    <div className="p-5 space-y-4 max-w-[1400px] mx-auto">
      {/* Hero: portfolio summary if available, else conversational welcome */}
      {hasPortfolio ? (
        <PortfolioHero summary={portfolioSummary} loading={loading} />
      ) : (
        <WelcomePortal data={sinceLastVisit} profile={userProfile} loading={loading} username={user?.username} />
      )}

      {/* Unified Multi-Broker Portfolio — aggregated view across all connected brokers */}
      {hasPortfolio && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <UnifiedPortfolioHero />
          <div className="space-y-4">
            <PortfolioHeatmap />
            <NetExposurePanel />
          </div>
        </div>
      )}

      {/* Auto-Pilot — one-click personalized trading plan */}
      <AutoPilotWidget profile={userProfile} />

      {/* Main content: 2/3 + 1/3 on widescreen */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          {/* Market pulse */}
          <div className="grid grid-cols-2 gap-3">
            <div className="panel p-3 card-hover">
              <h3 className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5 tracking-wide">
                {t("dashboard.btcDominance")}
              </h3>
              <DominanceChart data={dominance} loading={loading} />
            </div>
            <div className="panel p-3 card-hover">
              <h3 className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5 tracking-wide">
                {t("dashboard.market")}
              </h3>
              <RegimeBanner overview={overview} loading={loading} />
            </div>
          </div>

          {/* What to review today */}
          <TodayPriorities data={priorities} loading={loading} />

          {/* AI activity + signals */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <AIActivityTimeline data={activity} loading={loading} />
            <div className="panel p-4 card-hover">
              <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3">{t("dashboard.activeSignals")}</h3>
              {loading ? <LoadingSkeleton lines={3} /> : <SignalList signals={signals} />}
            </div>
          </div>

          {/* Daily report */}
          <DailyReportCard report={report} loading={loading} />
        </div>

        {/* Sidebar column */}
        <div className="space-y-4">
          {/* Smart Alerts — AI-powered proactive alerts */}
          <SmartAlertsPanel />

          {/* Copilot Suggestions — proactive portfolio suggestions */}
          <CopilotSuggestionsPanel />

          <div className="panel p-4 card-hover">
            <Watchlist />
          </div>
          {/* Alvora advisor chat */}
          <AlvoraSection />
        </div>
      </div>
    </div>
  );
}
