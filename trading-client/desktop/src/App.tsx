import { useState } from "react";
import { useAuth } from "./hooks/useAuth";
import { ThemeProvider } from "./theme/ThemeContext";
import { LoginScreen } from "./components/auth/LoginScreen";
import { Layout, type TabId } from "./components/layout/Layout";
import { Toast } from "./components/ui/Toast";
import { OverviewPage } from "./pages/OverviewPage";
import { ActivityPage } from "./pages/ActivityPage";
import { PositionsPage } from "./pages/PositionsPage";
import { PerformancePage } from "./pages/PerformancePage";
import { MarketPage } from "./pages/MarketPage";
import { AIAgentPage } from "./pages/AIAgentPage";
import { SettingsPage } from "./pages/SettingsPage";
import { logger } from "./lib/logger";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Global error handlers
window.addEventListener("error", (e) => {
  logger.error("Uncaught error", e.message + " | " + (e.filename || "") + ":" + (e.lineno || ""));
});

window.addEventListener("unhandledrejection", (e) => {
  const reason = e.reason?.message || e.reason || "Unknown";
  logger.error("Unhandled promise rejection", String(reason));
});

function AppContent() {
  const { user, loading } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)]">
        <div className="text-[var(--color-text-muted)]">Cargando...</div>
      </div>
    );
  }

  if (!user) {
    return <LoginScreen />;
  }

  const pages: Record<TabId, React.ReactNode> = {
    overview: <OverviewPage />,
    activity: <ActivityPage />,
    positions: <PositionsPage />,
    performance: <PerformancePage />,
    market: <MarketPage />,
    ai: <AIAgentPage />,
    settings: <SettingsPage />,
  };

  return (
    <Layout activeTab={activeTab} onTabChange={setActiveTab}>
      {pages[activeTab]}
    </Layout>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AppContent />
        <Toast />
      </ThemeProvider>
    </ErrorBoundary>
  );
}
