import { useState, useEffect, lazy, Suspense } from "react";
import { ThemeProvider } from "./theme/ThemeContext";
import { LoginScreen } from "./components/auth/LoginScreen";
import { Layout, type TabId } from "./components/layout/Layout";
import { Toast } from "./components/ui/Toast";
import { DashboardPage } from "./pages/DashboardPage";
import { logger } from "./lib/logger";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AuthProvider, useAuthContext } from "./context/AuthContext";
import { BrokerProvider, useBrokerContext } from "./context/BrokerContext";
import { BrokerOnboarding } from "./components/brokers/BrokerOnboarding";

const IntelligencePage = lazy(() => import("./pages/IntelligencePage").then(m => ({ default: m.IntelligencePage })));
const RisksPage = lazy(() => import("./pages/RisksPage").then(m => ({ default: m.RisksPage })));
const NewsPage = lazy(() => import("./pages/NewsPage").then(m => ({ default: m.NewsPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then(m => ({ default: m.ReportsPage })));
const BacktestPage = lazy(() => import("./pages/BacktestPage").then(m => ({ default: m.BacktestPage })));
const AIAgentPage = lazy(() => import("./pages/AIAgentPage").then(m => ({ default: m.AIAgentPage })));
const BotsPage = lazy(() => import("./pages/BotsPage").then(m => ({ default: m.BotsPage })));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage").then(m => ({ default: m.NotificationsPage })));
const ConnectionsPage = lazy(() => import("./pages/ConnectionsPage").then(m => ({ default: m.ConnectionsPage })));
const SecurityPage = lazy(() => import("./pages/SecurityPage").then(m => ({ default: m.SecurityPage })));
const PreferencesPage = lazy(() => import("./pages/PreferencesPage").then(m => ({ default: m.PreferencesPage })));

window.addEventListener("error", (e) => {
  logger.error("Uncaught error", e.message + " | " + (e.filename || "") + ":" + (e.lineno || ""));
});

window.addEventListener("unhandledrejection", (e) => {
  const reason = e.reason?.message || e.reason || "Unknown";
  logger.error("Unhandled promise rejection", String(reason));
});

function AppContent() {
  const { user, loading, login, register } = useAuthContext();
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [brokerSkipped, setBrokerSkipped] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)]">
        <div className="text-[var(--color-text-muted)]">Cargando...</div>
      </div>
    );
  }

  if (!user) {
    return <LoginScreen onLogin={login} onRegister={register} />;
  }

  return (
    <BrokerProvider>
      <BrokerAwareContent
        activeTab={activeTab}
        onTabChange={setActiveTab}
        showOnboarding={showOnboarding}
        onOnboardingDone={() => setShowOnboarding(false)}
        brokerSkipped={brokerSkipped}
        onBrokerSkip={() => setBrokerSkipped(true)}
      />
    </BrokerProvider>
  );
}

function BrokerAwareContent({
  activeTab,
  onTabChange,
  showOnboarding,
  onOnboardingDone,
  brokerSkipped,
  onBrokerSkip,
}: {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  showOnboarding: boolean;
  onOnboardingDone: () => void;
  brokerSkipped: boolean;
  onBrokerSkip: () => void;
}) {
  const { hasConnectedAccounts, isLoading } = useBrokerContext();
  const [visitedTabs, setVisitedTabs] = useState<Set<TabId>>(new Set(["dashboard"]));

  console.log("[App] BrokerAwareContent:", { hasConnectedAccounts, isLoading, showOnboarding, brokerSkipped });

  useEffect(() => {
    setVisitedTabs((prev) => {
      if (prev.has(activeTab)) return prev;
      const next = new Set(prev);
      next.add(activeTab);
      return next;
    });
  }, [activeTab]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)]">
        <div className="text-[var(--color-text-muted)]">Cargando...</div>
      </div>
    );
  }

  if ((!hasConnectedAccounts && !brokerSkipped) || showOnboarding) {
    return <BrokerOnboarding onConnected={onOnboardingDone} onSkip={onBrokerSkip} />;
  }

  const tabs: TabId[] = ["dashboard", "intelligence", "risks", "news", "reports", "backtest", "ai-agent", "bots", "alerts", "connections", "security", "preferences"];

  const pages: Record<TabId, React.ReactNode> = {
    dashboard: <DashboardPage />,
    intelligence: <IntelligencePage />,
    risks: <RisksPage />,
    news: <NewsPage />,
    reports: <ReportsPage />,
    backtest: <BacktestPage />,
    "ai-agent": <AIAgentPage />,
    "bots": <BotsPage />,
    alerts: <NotificationsPage onNavigate={(page) => onTabChange(page as TabId)} />,
    connections: <ConnectionsPage />,
    security: <SecurityPage />,
    preferences: <PreferencesPage />,
    broker: null,
  };

  return (
    <Layout activeTab={activeTab} onTabChange={onTabChange}>
      {tabs.map((tab) => (
        <div key={tab} style={{ display: tab === activeTab ? "block" : "none" }}>
          {visitedTabs.has(tab) ? (
            <Suspense fallback={<div className="flex items-center justify-center py-20 text-[var(--color-text-muted)] text-[13px]">Cargando...</div>}>
              {pages[tab]}
            </Suspense>
          ) : null}
        </div>
      ))}
    </Layout>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <AppContent />
          <Toast />
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
