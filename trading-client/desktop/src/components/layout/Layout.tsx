import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  LayoutDashboard,
  Activity,
  Wallet,
  TrendingUp,
  Store as MarketIcon,
  Bot,
  Settings as SettingsIcon,
  Sun,
  Moon,
  LogOut,
  Search,
  Bell,
  PanelLeftClose,
  PanelLeftOpen,
  CircleUser,
} from "lucide-react";
import { cn, fmtDate } from "../../lib/utils";
import { api } from "../../lib/api";
import { useTheme } from "../../theme/ThemeContext";
import { useAuthContext } from "../../context/AuthContext";
import { Badge } from "../ui/Badge";

export type TabId =
  | "overview"
  | "activity"
  | "positions"
  | "performance"
  | "market"
  | "ai"
  | "settings";

interface NavItem {
  id: TabId;
  label: string;
  icon: ReactNode;
  group: "trading" | "cuenta";
}

const navItems: NavItem[] = [
  {
    id: "overview",
    label: "Dashboard",
    icon: <LayoutDashboard size={17} />,
    group: "trading",
  },
  {
    id: "market",
    label: "Mercado",
    icon: <MarketIcon size={17} />,
    group: "trading",
  },
  {
    id: "positions",
    label: "Posiciones",
    icon: <Wallet size={17} />,
    group: "trading",
  },
  {
    id: "activity",
    label: "Actividad",
    icon: <Activity size={17} />,
    group: "trading",
  },
  {
    id: "performance",
    label: "Performance",
    icon: <TrendingUp size={17} />,
    group: "trading",
  },
  { id: "ai", label: "AI Agent", icon: <Bot size={17} />, group: "trading" },
  {
    id: "settings",
    label: "Ajustes",
    icon: <SettingsIcon size={17} />,
    group: "cuenta",
  },
];

const pageMeta: Record<TabId, { title: string; subtitle: string }> = {
  overview: { title: "Dashboard", subtitle: "Vista general de la operación" },
  market: { title: "Mercado", subtitle: "Movers y precios en vivo" },
  positions: { title: "Posiciones", subtitle: "Exposición abierta y órdenes" },
  activity: { title: "Actividad", subtitle: "Señales, trades y eventos" },
  performance: { title: "Performance", subtitle: "Métricas y equity" },
  ai: { title: "AI Agent", subtitle: "Configuración y bitácora del agente" },
  settings: { title: "Ajustes", subtitle: "Cuenta, riesgo y conexiones" },
};

interface LayoutProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  children: ReactNode;
}

export function Layout({ activeTab, onTabChange, children }: LayoutProps) {
  const { theme, toggleTheme } = useTheme();
  const { user, logout, authServerOk } = useAuthContext();

  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [signals, setSignals] = useState<any[]>([]);
  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const s = await api<any[]>("/api/signals");
        if (alive) setSignals(s.slice(-8).reverse());
      } catch {}
    };
    load();
    const id = setInterval(load, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

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

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return navItems.filter((n) => n.label.toLowerCase().includes(q));
  }, [query]);

  const meta = pageMeta[activeTab];
  const groups: { key: NavItem["group"]; label: string }[] = [
    { key: "trading", label: "Trading" },
    { key: "cuenta", label: "Cuenta" },
  ];

  return (
    <div className="flex h-screen bg-[var(--color-bg)] overflow-hidden">
      {/* ---------- Sidebar ---------- */}
      <aside
        className={cn(
          "flex-shrink-0 flex flex-col bg-[var(--color-surface)] transition-[width] duration-200",
          collapsed ? "w-[68px]" : "w-[228px]"
        )}
      >
        {/* Brand */}
        <div
          className={cn(
            "flex items-center h-16 flex-shrink-0",
            collapsed ? "justify-center px-2" : "gap-2.5 px-4"
          )}
        >
          <div className="w-9 h-9 rounded-[11px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center shadow-lg shadow-[var(--color-primary)]/25 flex-shrink-0">
            <span className="text-white font-extrabold text-[15px]">A</span>
          </div>
          {!collapsed && (
            <div className="leading-none min-w-0">
              <div className="font-extrabold text-[16px] text-[var(--color-text)] tracking-tight truncate">
                Alvora
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-[0.12em] mt-1">
                AI Trading
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
          {groups.map((g) => (
            <div key={g.key}>
              {!collapsed && (
                <div className="px-2.5 pb-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                  {g.label}
                </div>
              )}
              <div className="space-y-0.5">
                {navItems
                  .filter((n) => n.group === g.key)
                  .map((item) => {
                    const active = activeTab === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => onTabChange(item.id)}
                        title={collapsed ? item.label : undefined}
                        className={cn(
                          "relative w-full flex items-center rounded-[10px] text-[13px] font-semibold transition-all",
                          collapsed
                            ? "justify-center h-10"
                            : "gap-2.5 px-2.5 h-10",
                          active
                            ? "bg-[var(--color-primary)]/12 text-[var(--color-primary)]"
                            : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                        )}
                      >
                        {active && (
                          <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r bg-[var(--color-primary)]" />
                        )}
                        {item.icon}
                        {!collapsed && <span>{item.label}</span>}
                      </button>
                    );
                  })}
              </div>
            </div>
          ))}
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
              collapsed ? "justify-center" : "gap-2.5 px-2.5"
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
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex-shrink-0 h-16 flex items-center gap-4 px-5 bg-[var(--color-surface)]">
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
                      onTabChange(r.id);
                      setQuery("");
                    }}
                    className="w-full flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                  >
                    {r.icon}
                    {r.label}
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
                {signals.length > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-[var(--color-danger)] text-white text-[10px] font-bold flex items-center justify-center">
                    {signals.length}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute z-30 right-0 top-11 w-[300px] panel overflow-hidden">
                  <div className="px-3 py-2.5 border-b border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)]">
                    Señales recientes
                  </div>
                  <div className="max-h-[280px] overflow-y-auto divide-y divide-[var(--color-border)]">
                    {signals.length === 0 ? (
                      <div className="px-3 py-6 text-center text-[12px] text-[var(--color-text-muted)]">
                        Sin novedades
                      </div>
                    ) : (
                      signals.map((s) => (
                        <button
                          key={s.id}
                          onClick={() => {
                            onTabChange("activity");
                            setNotifOpen(false);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[var(--color-surface-hover)] text-left"
                        >
                          <Badge
                            variant={
                              s.signal_type === "BUY"
                                ? "success"
                                : s.signal_type === "SELL"
                                  ? "danger"
                                  : "default"
                            }
                          >
                            {s.signal_type}
                          </Badge>
                          <span className="text-[12px] font-bold text-[var(--color-text)] flex-1 truncate">
                            {s.symbol}
                          </span>
                          <span className="num text-[10px] text-[var(--color-text-muted)]">
                            {fmtDate(s.timestamp)}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
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
                      onTabChange("settings");
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

        <main className="flex-1 overflow-y-auto min-h-0">{children}</main>
      </div>
    </div>
  );
}
