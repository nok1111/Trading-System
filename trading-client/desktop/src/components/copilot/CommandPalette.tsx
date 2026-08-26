import { useEffect, useState, useRef, useMemo } from "react";
import {
  Search,
  LayoutDashboard,
  Brain,
  ShieldAlert,
  Newspaper,
  FileText,
  Bell,
  Plug,
  Shield,
  Settings,
  Bot,
  Grid3x3,
  Users,
  FlaskConical,
  LineChart,
  Scale,
  Target,
  AlertTriangle,
  Sparkles,
  CornerDownLeft,
} from "lucide-react";
import type { TabId } from "../layout/Layout";

interface CommandItem {
  id: string;
  label: string;
  subtitle?: string;
  icon: typeof Search;
  group: "navigation" | "actions" | "ai";
  action: () => void;
  keywords?: string[];
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (tab: TabId) => void;
  onQuickAction?: (action: string) => void;
}

export function CommandPalette({ open, onClose, onNavigate, onQuickAction }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Reset on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Build commands
  const commands: CommandItem[] = useMemo(() => {
    const navCommands: CommandItem[] = [
      { id: "nav-dashboard", label: "Dashboard", subtitle: "Vista general", icon: LayoutDashboard, group: "navigation", action: () => onNavigate("dashboard"), keywords: ["home", "inicio"] },
      { id: "nav-ai-agent", label: "AI Trading Agent", subtitle: "Agente autónomo", icon: Bot, group: "navigation", action: () => onNavigate("ai-agent"), keywords: ["ai", "agent", "bot"] },
      { id: "nav-agent-transparency", label: "Agent Performance", subtitle: "Transparencia IA", icon: LineChart, group: "navigation", action: () => onNavigate("agent-transparency"), keywords: ["performance", "stats"] },
      { id: "nav-bots", label: "Trading Bots", subtitle: "Grid y DCA bots", icon: Grid3x3, group: "navigation", action: () => onNavigate("bots"), keywords: ["grid", "dca", "bot"] },
      { id: "nav-intelligence", label: "Market Intelligence", subtitle: "Análisis de mercado", icon: Brain, group: "navigation", action: () => onNavigate("intelligence"), keywords: ["market", "analysis"] },
      { id: "nav-risks", label: "Alertas y Riesgos", subtitle: "Gestión de riesgo", icon: ShieldAlert, group: "navigation", action: () => onNavigate("risks"), keywords: ["risk", "alert", "peligro"] },
      { id: "nav-news", label: "Noticias", subtitle: "Feed de noticias", icon: Newspaper, group: "navigation", action: () => onNavigate("news"), keywords: ["news", "noticias"] },
      { id: "nav-reports", label: "Reportes", subtitle: "Reportes IA", icon: FileText, group: "navigation", action: () => onNavigate("reports"), keywords: ["report", "reporte"] },
      { id: "nav-backtest", label: "Backtest", subtitle: "Prueba estrategias", icon: FlaskConical, group: "navigation", action: () => onNavigate("backtest"), keywords: ["backtest", "test"] },
      { id: "nav-social", label: "Social Trading", subtitle: "Copy trading", icon: Users, group: "navigation", action: () => onNavigate("social"), keywords: ["social", "copy"] },
      { id: "nav-connections", label: "Conexiones", subtitle: "Gestión de brokers", icon: Plug, group: "navigation", action: () => onNavigate("connections"), keywords: ["broker", "connection"] },
      { id: "nav-alerts", label: "Notificaciones", subtitle: "Centro de notificaciones", icon: Bell, group: "navigation", action: () => onNavigate("alerts"), keywords: ["notification", "alert"] },
      { id: "nav-security", label: "Seguridad", subtitle: "2FA y sesiones", icon: Shield, group: "navigation", action: () => onNavigate("security"), keywords: ["security", "2fa", "totp"] },
      { id: "nav-preferences", label: "Preferencias", subtitle: "Ajustes", icon: Settings, group: "navigation", action: () => onNavigate("preferences"), keywords: ["settings", "config"] },
    ];

    const aiCommands: CommandItem[] = onQuickAction ? [
      { id: "ai-rebalance", label: "Rebalancear Portfolio", subtitle: "Sugerencia de IA", icon: Scale, group: "ai", action: () => onQuickAction("rebalance"), keywords: ["rebalance", "portfolio"] },
      { id: "ai-risk", label: "Chequeo de Riesgo IA", subtitle: "Evaluación completa", icon: AlertTriangle, group: "ai", action: () => onQuickAction("risk_check"), keywords: ["risk", "check", "peligro"] },
      { id: "ai-opportunity", label: "Escanear Oportunidades", subtitle: "IA busca oportunidades", icon: Target, group: "ai", action: () => onQuickAction("opportunity_scan"), keywords: ["opportunity", "scan", "oportunidad"] },
      { id: "ai-review", label: "Revisar Posiciones", subtitle: "IA revisa todas las posiciones", icon: Sparkles, group: "ai", action: () => onQuickAction("close_all_review"), keywords: ["review", "position", "posicion"] },
    ] : [];

    return [...navCommands, ...aiCommands];
  }, [onNavigate, onQuickAction]);

  // Filter by query
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((cmd) => {
      if (cmd.label.toLowerCase().includes(q)) return true;
      if (cmd.subtitle?.toLowerCase().includes(q)) return true;
      if (cmd.keywords?.some((k) => k.includes(q))) return true;
      return false;
    });
  }, [commands, query]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const cmd = filtered[selectedIndex];
        if (cmd) {
          cmd.action();
          onClose();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, selectedIndex, onClose]);

  // Scroll selected into view
  useEffect(() => {
    if (!listRef.current) return;
    const selected = listRef.current.children[selectedIndex] as HTMLElement;
    if (selected) {
      selected.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!open) return null;

  // Group filtered results
  const groups = {
    navigation: filtered.filter((c) => c.group === "navigation"),
    ai: filtered.filter((c) => c.group === "ai"),
  };

  let runningIndex = 0;

  const renderGroup = (group: "navigation" | "ai", items: CommandItem[]) => {
    if (items.length === 0) return null;
    return (
      <div key={group} className="mb-1">
        <div className="px-3 py-1 text-[10px] font-bold uppercase text-[var(--color-text-muted)] tracking-wide">
          {group === "navigation" ? "Navegación" : "Acciones IA"}
        </div>
        {items.map((cmd) => {
          const idx = runningIndex++;
          const isSelected = idx === selectedIndex;
          const Icon = cmd.icon;
          return (
            <button
              key={cmd.id}
              onMouseEnter={() => setSelectedIndex(idx)}
              onClick={() => {
                cmd.action();
                onClose();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
                isSelected ? "bg-[var(--color-primary)]/15" : "hover:bg-[var(--color-surface-2)]"
              }`}
            >
              <Icon size={16} className={isSelected ? "text-[var(--color-primary)]" : "text-[var(--color-text-muted)]"} />
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold text-[var(--color-text)] truncate">
                  {cmd.label}
                </div>
                {cmd.subtitle && (
                  <div className="text-[11px] text-[var(--color-text-muted)] truncate">
                    {cmd.subtitle}
                  </div>
                )}
              </div>
              {isSelected && (
                <CornerDownLeft size={12} className="text-[var(--color-text-muted)]" />
              )}
            </button>
          );
        })}
      </div>
    );
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-[100] flex items-start justify-center pt-[15vh]"
        onClick={onClose}
      >
        {/* Palette */}
        <div
          className="w-full max-w-[560px] mx-4 bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] shadow-2xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)]">
            <Search size={18} className="text-[var(--color-text-muted)]" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Buscar páginas o acciones..."
              className="flex-1 bg-transparent text-[14px] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] outline-none"
            />
            <kbd className="text-[10px] text-[var(--color-text-muted)] px-1.5 py-0.5 rounded border border-[var(--color-border)]">
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-[400px] overflow-y-auto py-2">
            {filtered.length === 0 ? (
              <div className="px-4 py-8 text-center text-[12px] text-[var(--color-text-muted)]">
                No se encontraron resultados para "{query}"
              </div>
            ) : (
              <>
                {renderGroup("navigation", groups.navigation)}
                {renderGroup("ai", groups.ai)}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-[var(--color-border)] flex items-center justify-between text-[10px] text-[var(--color-text-muted)]">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-[var(--color-border)]">↑↓</kbd>
                navegar
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 py-0.5 rounded border border-[var(--color-border)]">↵</kbd>
                seleccionar
              </span>
            </div>
            <span>Alvora Copilot</span>
          </div>
        </div>
      </div>
    </>
  );
}
