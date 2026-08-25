import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import alvoraLogo from "../../assets/alvora-logo.png";
import {
  LayoutDashboard,
  Brain,
  ShieldAlert,
  Newspaper,
  FileText,
  Bell,
  Plug,
  Shield,
  Settings as SettingsIcon,
  Sun,
  Moon,
  LogOut,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  CircleUser,
  FlaskConical,
  Bot,
  Grid3x3,
  Users,
  Menu,
  X,
  LineChart,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useTheme } from "../../theme/ThemeContext";
import { useI18n } from "../../i18n/I18nContext";
import { useAuthContext } from "../../context/AuthContext";
import { useBrokerContext } from "../../context/BrokerContext";
import { Badge } from "../ui/Badge";
import { MarketStatusBar } from "./MarketStatusBar";
import { BrokerListGroup } from "../brokers/BrokerListGroup";
import { BrokerConnectModal } from "../brokers/BrokerConnectModal";
import { BrokerPage } from "../../pages/BrokerPage";
import { NotificationDropdown } from "./NotificationDropdown";
import { NotificationToasts } from "./NotificationToasts";
import { AlvoraFloatingWidget } from "../alvora/AlvoraFloatingWidget";
import { getUnreadNotificationCount } from "../../lib/intelligenceApi";
import { api } from "../../lib/api";
import {
  isBrokerConnected,
  isBrokerDegraded,
  type SupportedBroker,
  type BrokerAccount,
} from "../../lib/brokerTypes";

export type TabId =
  | "dashboard"
  | "intelligence"
  | "risks"
  | "news"
  | "reports"
  | "backtest"
  | "alerts"
  | "connections"
  | "security"
  | "preferences"
  | "broker"
  | "ai-agent"
  | "agent-transparency"
  | "bots"
  | "social";

interface NavItem {
  id: TabId;
  labelKey: string;
  icon: ReactNode;
  group: "trading" | "analytics" | "sistema";
}

const tradingItems: NavItem[] = [
  { id: "dashboard", labelKey: "nav.dashboard", icon: <LayoutDashboard size={17} />, group: "trading" },
  { id: "ai-agent", labelKey: "nav.aiAgent", icon: <Bot size={17} />, group: "trading" },
  { id: "agent-transparency", labelKey: "nav.agentPerformance", icon: <LineChart size={17} />, group: "trading" },
  { id: "bots", labelKey: "nav.bots", icon: <Grid3x3 size={17} />, group: "trading" },
  { id: "connections", labelKey: "nav.connections", icon: <Plug size={17} />, group: "trading" },
];

const analyticsItems: NavItem[] = [
  { id: "intelligence", labelKey: "nav.intelligence", icon: <Brain size={17} />, group: "analytics" },
  { id: "risks", labelKey: "nav.security", icon: <ShieldAlert size={17} />, group: "analytics" },
  { id: "news", labelKey: "nav.news", icon: <Newspaper size={17} />, group: "analytics" },
  { id: "reports", labelKey: "nav.reports", icon: <FileText size={17} />, group: "analytics" },
  { id: "backtest", labelKey: "nav.backtest", icon: <FlaskConical size={17} />, group: "analytics" },
  { id: "social", labelKey: "nav.social", icon: <Users size={17} />, group: "analytics" },
];

const sistemaItems: NavItem[] = [
  { id: "alerts", labelKey: "nav.alerts", icon: <Bell size={17} />, group: "sistema" },
  { id: "security", labelKey: "nav.security", icon: <Shield size={17} />, group: "sistema" },
  { id: "preferences", labelKey: "nav.preferences", icon: <SettingsIcon size={17} />, group: "sistema" },
];

const pageMeta: Record<TabId, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Vista general del mercado e inteligencia" },
  intelligence: { title: "Market Intelligence", subtitle: "Análisis profundo de mercado" },
  risks: { title: "Alertas y Riesgos", subtitle: "Crash risk, whale alerts, alertas de precio y gestión de riesgo" },
  news: { title: "Noticias", subtitle: "Feed de noticias con sentiment" },
  reports: { title: "Reportes", subtitle: "Reportes periódicos generados por IA" },
  backtest: { title: "Backtest", subtitle: "Prueba estrategias con datos históricos" },
  alerts: { title: "Notificaciones", subtitle: "Centro de notificaciones del sistema" },
  connections: { title: "Conexiones", subtitle: "Gestión de brokers" },
  security: { title: "Seguridad", subtitle: "Configuración de seguridad" },
  preferences: { title: "Preferencias", subtitle: "Ajustes de la aplicación" },
  broker: { title: "Broker", subtitle: "Vista de broker" },
  "ai-agent": { title: "AI Trading Agent", subtitle: "Agente de IA autónomo — razonamiento y estadísticas" },
  "agent-transparency": { title: "Agent Performance", subtitle: "Transparencia y performance attribution del AI Agent" },
  bots: { title: "Trading Bots", subtitle: "Grid y DCA bots automatizados" },
  social: { title: "Social Trading", subtitle: "Copia señales de traders top en tu broker" },
};

interface LayoutProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  children: ReactNode;
}

export function Layout({ activeTab, onTabChange, children }: LayoutProps) {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  const { user, logout, authServerOk } = useAuthContext();
  const { supportedBrokers, connectedAccounts } = useBrokerContext();

  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [newReportsCount, setNewReportsCount] = useState(0);
  const [expandedBrokers, setExpandedBrokers] = useState<Set<string>>(new Set());
  const [connectModalBroker, setConnectModalBroker] = useState<SupportedBroker | null>(null);
  const [selectedBrokerModule, setSelectedBrokerModule] = useState<{ brokerId: string; moduleId: string } | null>(null);
  const [presetTradeSymbol, setPresetTradeSymbol] = useState<string | undefined>(undefined);
  const [presetStopLoss, setPresetStopLoss] = useState<number | undefined>(undefined);
  const [presetTakeProfit, setPresetTakeProfit] = useState<number | undefined>(undefined);
  const [presetReason, setPresetReason] = useState<string | undefined>(undefined);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  // Detect mobile viewport
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // Close mobile nav when tab changes
  const handleTabChange = (tab: TabId) => {
    onTabChange(tab);
    setMobileNavOpen(false);
  };

  useEffect(() => {
    const onNavigate = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.page === "trade" && detail?.asset) {
        const firstConnected = connectedAccounts.find((a) => isBrokerConnected(a.status));
        const brokerId = detail.broker || firstConnected?.brokerId || connectedAccounts[0]?.brokerId || "";
        const rawAsset = detail.asset.toUpperCase().replace("/", "");
        const QUOTES = ["USDT", "USDC", "FDUSD", "TUSD", "BUSD", "USD", "EUR", "BTC", "ETH", "BNB", "TRY", "BRL", "MXN", "JPY", "GBP", "AUD"];
        const symbol = QUOTES.some((q) => rawAsset.endsWith(q))
          ? rawAsset
          : rawAsset + "USDT";
        setSelectedBrokerModule({ brokerId, moduleId: "trade" });
        setPresetTradeSymbol(symbol);
        setPresetStopLoss(detail.stop_loss ?? undefined);
        setPresetTakeProfit(detail.take_profit ?? undefined);
        setPresetReason(undefined);
        // If signal data provided, fetch suggested trade from intelligence
        if (detail.signalType && detail.signalData) {
          api<any>("/api/intelligence/suggest-trade", {
            method: "POST",
            body: JSON.stringify({
              signal_type: detail.signalType,
              asset: detail.asset,
              signal_data: detail.signalData,
            }),
          }).then((r) => {
            if (r?.status === "ok") {
              setPresetReason(r.reason || undefined);
            }
          }).catch(() => {});
        }
        onTabChange("broker");
      } else if (detail?.page) {
        onTabChange(detail.page as TabId);
      }
    };
    window.addEventListener("navigate", onNavigate);
    return () => window.removeEventListener("navigate", onNavigate);
  }, [onTabChange, connectedAccounts]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const count = await getUnreadNotificationCount();
        if (alive) setUnreadCount(count);
      } catch {}
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Track new reports for badge on "Reportes" menu item
  useEffect(() => {
    let alive = true;
    const loadReportsCount = async () => {
      try {
        const r = await api<any[]>("/api/intelligence/reports/all");
        const currentCount = r?.length ?? 0;
        const lastSeen = parseInt(localStorage.getItem("reports_last_seen_count") || "", 10);
        if (alive) {
          if (isNaN(lastSeen)) {
            localStorage.setItem("reports_last_seen_count", String(currentCount));
            setNewReportsCount(0);
          } else if (currentCount > lastSeen) {
            setNewReportsCount(currentCount - lastSeen);
          }
        }
      } catch {}
    };
    loadReportsCount();
    const id = setInterval(loadReportsCount, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Reset reports badge when user visits the Reports page
  useEffect(() => {
    if (activeTab === "reports") {
      const loadAndReset = async () => {
        try {
          const r = await api<any[]>("/api/intelligence/reports/all");
          const currentCount = r?.length ?? 0;
          localStorage.setItem("reports_last_seen_count", String(currentCount));
          setNewReportsCount(0);
        } catch {}
      };
      loadAndReset();
    }
  }, [activeTab]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node))
        setNotifOpen(false);
      if (userRef.current && !userRef.current.contains(e.target as Node))
        setUserOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (connectedAccounts.length > 0 && expandedBrokers.size === 0) {
      setExpandedBrokers(new Set([connectedAccounts[0].brokerId]));
    }
  }, [connectedAccounts, expandedBrokers.size]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return [...tradingItems, ...analyticsItems, ...sistemaItems].filter((n) =>
      t(n.labelKey).toLowerCase().includes(q)
    );
  }, [query]);

  const sortedBrokers = useMemo(() => {
    const accountMap = new Map<string, BrokerAccount>();
    for (const acc of connectedAccounts) {
      if (!accountMap.has(acc.brokerId)) {
        accountMap.set(acc.brokerId, acc);
      }
    }
    return [...supportedBrokers].sort((a, b) => {
      const aStatus = accountMap.get(a.brokerId)?.status || "NOT_CONNECTED";
      const bStatus = accountMap.get(b.brokerId)?.status || "NOT_CONNECTED";
      const aConnected = isBrokerConnected(aStatus);
      const bConnected = isBrokerConnected(bStatus);
      const aDegraded = isBrokerDegraded(aStatus);
      const bDegraded = isBrokerDegraded(bStatus);
      if (aConnected && !bConnected) return -1;
      if (!aConnected && bConnected) return 1;
      if (aDegraded && !bDegraded) return -1;
      if (!aDegraded && bDegraded) return 1;
      return 0;
    });
  }, [supportedBrokers, connectedAccounts]);

  const toggleBroker = (brokerId: string) => {
    setExpandedBrokers((prev) => {
      const next = new Set(prev);
      if (next.has(brokerId)) next.delete(brokerId);
      else next.add(brokerId);
      return next;
    });
  };

  const meta = pageMeta[activeTab] || { title: "", subtitle: "" };

  return (
    <div className="flex h-screen bg-[var(--color-bg)] overflow-hidden">
      {/* Skip to content link for keyboard navigation */}
      <a href="#main-content" className="skip-link">
        Saltar al contenido
      </a>

      {/* ---------- Mobile overlay backdrop ---------- */}
      {isMobile && mobileNavOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* ---------- Sidebar ---------- */}
      <aside
        role="navigation"
        aria-label="Navegación principal"
        className={cn(
          "flex flex-col bg-[var(--color-surface)] transition-all duration-200 z-50",
          isMobile
            ? cn(
                "fixed inset-y-0 left-0 w-[228px]",
                mobileNavOpen ? "translate-x-0" : "-translate-x-full"
              )
            : cn(
                "flex-shrink-0",
                collapsed ? "w-[68px]" : "w-[228px]"
              )
        )}
      >
        {/* Brand */}
        <div
          className={cn(
            "flex items-center h-16 flex-shrink-0",
            collapsed && !isMobile ? "justify-center px-2" : "gap-2.5 px-4"
          )}
        >
          <div className="w-9 h-9 rounded-[11px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center shadow-lg shadow-[var(--color-primary)]/25 flex-shrink-0 overflow-hidden">
            <img src={alvoraLogo} alt="Alvora" className="w-full h-full object-contain" />
          </div>
          {(!collapsed || isMobile) && (
            <div className="leading-none min-w-0 flex-1">
              <div className="font-extrabold text-[16px] text-[var(--color-text)] tracking-tight truncate">
                Alvora
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-[0.12em] mt-1">
                AI Trading
              </div>
            </div>
          )}
          {/* Mobile close button */}
          {isMobile && (
            <button
              onClick={() => setMobileNavOpen(false)}
              className="flex items-center justify-center w-8 h-8 rounded-[8px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors flex-shrink-0"
              aria-label="Cerrar menú"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
          {/* TRADING */}
          <div>
            {!collapsed && (
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                Trading
              </div>
            )}
            <div className="space-y-0.5">
              {tradingItems.map((item) => {
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleTabChange(item.id)}
                    title={collapsed ? t(item.labelKey) : undefined}
                    className={cn(
                      "relative w-full flex items-center rounded-[10px] text-[13px] font-semibold transition-all",
                      collapsed ? "justify-center h-10" : "gap-2.5 px-2.5 h-10",
                      active
                        ? "bg-[var(--color-primary)]/12 text-[var(--color-primary)]"
                        : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-[var(--color-primary)]" />
                    )}
                    {item.icon}
                    {!collapsed && <span>{t(item.labelKey)}</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ANALYTICS */}
          <div>
            {!collapsed && (
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                Analytics
              </div>
            )}
            <div className="space-y-0.5">
              {analyticsItems.map((item) => {
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleTabChange(item.id)}
                    title={collapsed ? t(item.labelKey) : undefined}
                    className={cn(
                      "relative w-full flex items-center rounded-[10px] text-[13px] font-semibold transition-all",
                      collapsed ? "justify-center h-10" : "gap-2.5 px-2.5 h-10",
                      active
                        ? "bg-[var(--color-primary)]/12 text-[var(--color-primary)]"
                        : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-[var(--color-primary)]" />
                    )}
                    {item.icon}
                    {!collapsed && <span>{t(item.labelKey)}</span>}
                    {item.id === "reports" && newReportsCount > 0 && (
                      <span
                        className={cn(
                          "absolute min-w-[16px] h-4 px-1 rounded-full bg-[var(--color-primary)] text-white text-[11px] font-bold flex items-center justify-center",
                          collapsed ? "-top-0.5 -right-0.5" : "top-1/2 -translate-y-1/2 right-1.5"
                        )}
                      >
                        {newReportsCount > 99 ? "99+" : newReportsCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* MIS BROKERS */}
          <div>
            {!collapsed && (
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                Mis Brokers
              </div>
            )}
            <div className="space-y-0.5">
              {sortedBrokers.map((broker) => {
                const account = connectedAccounts.find((a) => a.brokerId === broker.brokerId) || null;
                return (
                  <BrokerListGroup
                    key={broker.brokerId}
                    broker={broker}
                    account={account}
                    expanded={expandedBrokers.has(broker.brokerId)}
                    onToggle={() => toggleBroker(broker.brokerId)}
                    onConnect={() => {
                      if (broker.implemented) {
                        setConnectModalBroker(broker);
                      }
                    }}
                    selectedModule={selectedBrokerModule?.brokerId === broker.brokerId ? selectedBrokerModule.moduleId : null}
                    onSelectModule={(moduleId) => {
                      setSelectedBrokerModule({ brokerId: broker.brokerId, moduleId });
                      handleTabChange("broker");
                    }}
                    collapsed={collapsed}
                  />
                );
              })}
            </div>
          </div>

          {/* SISTEMA */}
          <div>
            {!collapsed && (
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                Sistema
              </div>
            )}
            <div className="space-y-0.5">
              {sistemaItems.map((item) => {
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleTabChange(item.id)}
                    title={collapsed ? t(item.labelKey) : undefined}
                    className={cn(
                      "relative w-full flex items-center rounded-[10px] text-[13px] font-semibold transition-all",
                      collapsed ? "justify-center h-10" : "gap-2.5 px-2.5 h-10",
                      active
                        ? "bg-[var(--color-primary)]/12 text-[var(--color-primary)]"
                        : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-[var(--color-primary)]" />
                    )}
                    {item.icon}
                    {!collapsed && <span>{t(item.labelKey)}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        </nav>

        {/* Sidebar footer */}
        <div className="flex-shrink-0 p-2 space-y-0.5">
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Light mode" : "Dark mode"}
            className={cn(
              "w-full flex items-center rounded-[10px] h-10 text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors",
              collapsed ? "justify-center" : "gap-2.5 px-2.5"
            )}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            {!collapsed && <span>{theme === "dark" ? "Claro" : "Oscuro"}</span>}
          </button>
          <button
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? "Expandir" : "Colapsar"}
            className={cn(
              "w-full flex items-center rounded-[10px] h-10 text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors",
              collapsed ? "justify-center" : "gap-2.5 px-2.5",
              isMobile && "hidden"
            )}
          >
            {collapsed ? (
              <PanelLeftOpen size={17} />
            ) : (
              <PanelLeftClose size={17} />
            )}
            {!collapsed && <span>Colapsar</span>}
          </button>
          <button
            onClick={logout}
            title="Salir"
            className={cn(
              "w-full flex items-center rounded-[10px] h-10 text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 transition-colors",
              collapsed ? "justify-center" : "gap-2.5 px-2.5"
            )}
          >
            <LogOut size={17} />
            {!collapsed && <span>Cerrar sesión</span>}
          </button>
        </div>
      </aside>

      {/* ---------- Main ---------- */}
      <div id="main-content" className="flex-1 flex flex-col min-w-0" role="main">
        <MarketStatusBar />
        <header className="flex-shrink-0 h-14 flex items-center gap-4 px-5 bg-[var(--color-surface)] border-b border-[var(--color-border)]">
          {/* Mobile menu button */}
          {isMobile && (
            <button
              onClick={() => setMobileNavOpen(true)}
              className="flex items-center justify-center w-9 h-9 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors flex-shrink-0"
              aria-label="Abrir menú"
            >
              <Menu size={18} />
            </button>
          )}
          <div className="min-w-0">
            <h1 className="text-[18px] font-extrabold text-[var(--color-text)] tracking-tight leading-none truncate">
              {meta.title}
            </h1>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1 truncate">
              {meta.subtitle}
            </p>
          </div>

          {/* Search / quick jump */}
          <div className="relative flex-1 max-w-[420px] mx-auto">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] pointer-events-none"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar sección..."
              className="w-full h-9 pl-9 pr-3 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[13px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/15 placeholder:text-[var(--color-text-muted)] transition-all"
            />
            {results.length > 0 && (
              <div className="absolute z-30 top-11 left-0 right-0 panel p-1.5">
                {results.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => {
                      handleTabChange(r.id);
                      setQuery("");
                    }}
                    className="w-full flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                  >
                    {r.icon}
                    {t(r.labelKey)}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5 flex-shrink-0">
            {/* Backend status */}
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 h-9 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)]">
              <span className="relative flex w-2 h-2">
                {authServerOk && (
                  <span className="absolute inset-0 rounded-full bg-[var(--color-success)] animate-ping opacity-60" />
                )}
                <span
                  className={cn(
                    "relative w-2 h-2 rounded-full",
                    authServerOk
                      ? "bg-[var(--color-success)]"
                      : "bg-[var(--color-danger)]"
                  )}
                />
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                {authServerOk ? "Online" : "Offline"}
              </span>
            </div>

            {/* Notifications */}
            <div className="relative" ref={notifRef}>
              <button
                onClick={() => setNotifOpen((v) => !v)}
                className="relative flex items-center justify-center w-9 h-9 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                title="Notificaciones"
              >
                <Bell size={16} />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-[var(--color-danger)] text-white text-[10px] font-bold flex items-center justify-center">
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                )}
              </button>
              <NotificationDropdown
                open={notifOpen}
                onClose={() => setNotifOpen(false)}
                onNavigate={(page) => onTabChange(page as TabId)}
                onUnreadCountChange={setUnreadCount}
              />
            </div>

            {/* User */}
            <div className="relative" ref={userRef}>
              <button
                onClick={() => setUserOpen((v) => !v)}
                className="flex items-center gap-2 pl-1 pr-2 h-9 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] transition-colors"
              >
                <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-primary)] flex items-center justify-center text-white text-[12px] font-bold uppercase">
                  {user?.username?.[0] || "?"}
                </span>
                <span className="text-[13px] font-semibold text-[var(--color-text)] max-w-[110px] truncate hidden md:inline">
                  {user?.username || "--"}
                </span>
              </button>
              {userOpen && (
                <div className="absolute z-30 right-0 top-11 w-[220px] panel overflow-hidden">
                  <div className="px-3 py-3 border-b border-[var(--color-border)]">
                    <div className="flex items-center gap-2">
                      <CircleUser
                        size={16}
                        className="text-[var(--color-text-muted)]"
                      />
                      <span className="text-[13px] font-bold text-[var(--color-text)] truncate">
                        {user?.username || "--"}
                      </span>
                    </div>
                    {user && (
                      <div className="mt-2">
                        <Badge
                          variant={
                            user.subscription === "premium"
                              ? "warning"
                              : user.subscription === "pro"
                                ? "primary"
                                : "default"
                          }
                        >
                          {user.subscription}
                        </Badge>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      handleTabChange("preferences");
                      setUserOpen(false);
                    }}
                    className="w-full flex items-center gap-2.5 px-3 h-10 text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                  >
                    <SettingsIcon size={15} />
                    Ajustes
                  </button>
                  <button
                    onClick={logout}
                    className="w-full flex items-center gap-2.5 px-3 h-10 text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                  >
                    <LogOut size={15} />
                    Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto min-h-0">
          {activeTab === "broker" ? (
            <BrokerPage
              brokerId={selectedBrokerModule?.brokerId || null}
              moduleId={selectedBrokerModule?.moduleId || null}
              presetSymbol={presetTradeSymbol}
              presetStopLoss={presetStopLoss}
              presetTakeProfit={presetTakeProfit}
              presetReason={presetReason}
            />
          ) : (
            children
          )}
        </main>
      </div>

      {/* Connect modal */}
      {connectModalBroker && (
        <BrokerConnectModal
          broker={connectModalBroker}
          onClose={() => setConnectModalBroker(null)}
        />
      )}

      {/* Toast notifications */}
      <NotificationToasts />

      {/* Alvora floating advisor — available on all pages */}
      <AlvoraFloatingWidget />
    </div>
  );
}
