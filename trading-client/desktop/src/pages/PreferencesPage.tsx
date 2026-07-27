import { Sun, Moon, Bell, Globe, Server } from "lucide-react";
import { useTheme } from "../theme/ThemeContext";
import { useBrokerContext } from "../context/BrokerContext";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { isFeatureEnabled } from "../lib/featureFlags";
import type { FeatureFlag } from "../lib/featureFlags";

export function PreferencesPage() {
  const { theme, toggleTheme } = useTheme();
  const { supportedBrokers, connectedAccounts } = useBrokerContext();

  const flags: { flag: FeatureFlag; label: string }[] = [
    { flag: "brokerManagement", label: "Gestión de brokers" },
    { flag: "multiBroker", label: "Multi-broker" },
    { flag: "multipleAccountsPerBroker", label: "Múltiples cuentas por broker" },
    { flag: "signals", label: "Señales" },
    { flag: "alerts", label: "Alertas" },
    { flag: "agents", label: "Agentes IA" },
    { flag: "scenarios", label: "Escenarios" },
    { flag: "scheduler", label: "Scheduler" },
    { flag: "portfolioMatch", label: "Portfolio Match" },
    { flag: "reports", label: "Reportes" },
    { flag: "pending", label: "Notificaciones pendientes" },
  ];

  return (
    <div className="p-5 space-y-4 max-w-[700px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Preferencias</h2>

      {/* Appearance */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          {theme === "dark" ? <Moon size={18} /> : <Sun size={18} />}
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Apariencia</h3>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--color-text-muted)]">Tema</span>
          <Button variant="default" size="sm" onClick={toggleTheme}>
            {theme === "dark" ? "Cambiar a Claro" : "Cambiar a Oscuro"}
          </Button>
        </div>
      </div>

      {/* AI Server */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Server size={18} />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">AI Server</h3>
        </div>
        <div>
          <label className="block text-[12px] font-semibold text-[var(--color-text-muted)] mb-1.5">
            URL del AI Server
          </label>
          <Input
            type="text"
            defaultValue={localStorage.getItem("aiServerUrl") || "http://localhost:8000"}
            onBlur={(e) => localStorage.setItem("aiServerUrl", e.target.value)}
            className="w-full"
          />
        </div>
      </div>

      {/* Brokers summary */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Globe size={18} />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Brokers</h3>
        </div>
        <div className="grid grid-cols-2 gap-3 text-[12px]">
          <div>
            <span className="text-[var(--color-text-muted)]">Brokers soportados: </span>
            <span className="font-bold text-[var(--color-text)]">{supportedBrokers.length}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)]">Cuentas conectadas: </span>
            <span className="font-bold text-[var(--color-text)]">{connectedAccounts.length}</span>
          </div>
        </div>
      </div>

      {/* Feature flags */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Bell size={18} />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Módulos Activos</h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {flags.map(({ flag, label }) => (
            <div
              key={flag}
              className="flex items-center justify-between rounded-[8px] bg-[var(--color-surface-2)] px-3 h-8"
            >
              <span className="text-[12px] font-semibold text-[var(--color-text-muted)]">{label}</span>
              <span
                className={`text-[10px] font-bold uppercase ${
                  isFeatureEnabled(flag) ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]"
                }`}
              >
                {isFeatureEnabled(flag) ? "ON" : "OFF"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
