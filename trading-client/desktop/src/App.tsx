import { useState } from "react";
import { ThemeProvider } from "./theme/ThemeContext";
import { LoginScreen } from "./components/auth/LoginScreen";
import { Layout, type TabId } from "./components/layout/Layout";
import { Toast } from "./components/ui/Toast";
import { OverviewPage } from "./pages/OverviewPage";
import { ActivityPage } from "./pages/ActivityPage";
import { PositionsPage } from "./pages/PositionsPage";
import { PerformancePage } from "./pages/PerformancePage";
import { MarketPage } from "./pages/MarketPage";
import { WalletPage } from "./pages/WalletPage";
import { SettingsPage } from "./pages/SettingsPage";
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
    dashboard: <OverviewPage />,
    intelligence: <MarketPage />,
    opportunities: <ActivityPage />,
    risks: <PositionsPage />,
    news: <MarketPage />,
    reports: <PerformancePage />,
    alerts: <ActivityPage />,
    connections: <SettingsPage />,
    security: <SettingsPage />,
    preferences: <SettingsPage />,
    broker: <WalletPage />,
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
