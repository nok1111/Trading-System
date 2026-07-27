import { useState } from "react";
import { ThemeProvider } from "./theme/ThemeContext";
import { LoginScreen } from "./components/auth/LoginScreen";
import { Layout, type TabId } from "./components/layout/Layout";
import { Toast } from "./components/ui/Toast";
import { DashboardPage } from "./pages/DashboardPage";
import { IntelligencePage } from "./pages/IntelligencePage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { RisksPage } from "./pages/RisksPage";
import { NewsPage } from "./pages/NewsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { ConnectionsPage } from "./pages/ConnectionsPage";
import { SecurityPage } from "./pages/SecurityPage";
import { PreferencesPage } from "./pages/PreferencesPage";
import { logger } from "./lib/logger";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AuthProvider, useAuthContext } from "./context/AuthContext";
import { BrokerProvider, useBrokerContext } from "./context/BrokerContext";
import { BrokerOnboarding } from "./components/brokers/BrokerOnboarding";

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
      />
    </BrokerProvider>
  );
}

function BrokerAwareContent({
  activeTab,
  onTabChange,
  showOnboarding,
  onOnboardingDone,
}: {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  showOnboarding: boolean;
  onOnboardingDone: () => void;
}) {
  const { hasConnectedAccounts, isLoading } = useBrokerContext();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)]">
        <div className="text-[var(--color-text-muted)]">Cargando...</div>
      </div>
    );
  }

  if (!hasConnectedAccounts || showOnboarding) {
    return <BrokerOnboarding onConnected={onOnboardingDone} />;
  }

  const tabs: TabId[] = ["dashboard", "intelligence", "opportunities", "risks", "news", "reports", "alerts", "connections", "security", "preferences"];

  const pages: Record<TabId, React.ReactNode> = {
    dashboard: <DashboardPage />,
    intelligence: <IntelligencePage />,
    opportunities: <OpportunitiesPage />,
    risks: <RisksPage />,
    news: <NewsPage />,
    reports: <ReportsPage />,
    alerts: <AlertsPage />,
    connections: <ConnectionsPage />,
    security: <SecurityPage />,
    preferences: <PreferencesPage />,
    broker: null,
  };

  return (
    <Layout activeTab={activeTab} onTabChange={onTabChange}>
      {tabs.map((tab) => (
        <div key={tab} style={{ display: tab === activeTab ? "block" : "none" }}>
          {pages[tab]}
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
