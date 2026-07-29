import { Sun, Moon, Bell, Globe, Server, Rocket, Shield, Wallet, Target, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { useTheme } from "../theme/ThemeContext";
import { useBrokerContext } from "../context/BrokerContext";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { isFeatureEnabled } from "../lib/featureFlags";
import type { FeatureFlag } from "../lib/featureFlags";
import { getUserProfile, saveUserProfile, type UserProfileData } from "../lib/intelligenceApi";
import { cn } from "../lib/utils";

const EXPERIENCE_OPTIONS = [
  { value: "beginner", label: "Principiante", icon: "🌱" },
  { value: "intermediate", label: "Intermedio", icon: "📈" },
  { value: "advanced", label: "Avanzado", icon: "🚀" },
];

const RISK_OPTIONS = [
  { value: "conservative", label: "Conservador", icon: "🛡️" },
  { value: "moderate", label: "Moderado", icon: "⚖️" },
  { value: "aggressive", label: "Agresivo", icon: "🔥" },
];

const ASSET_OPTIONS = [
  { value: "crypto", label: "Cripto", icon: "₿" },
  { value: "stocks", label: "Acciones", icon: "📊" },
  { value: "forex", label: "Forex", icon: "💱" },
  { value: "commodities", label: "Oro/Commodities", icon: "🥇" },
];

const CAPITAL_OPTIONS = [
  { value: "<100", label: "< $100" },
  { value: "100-1000", label: "$100 - $1K" },
  { value: "1000-10000", label: "$1K - $10K" },
  { value: "10000-50000", label: "$10K - $50K" },
  { value: "50000+", label: "> $50K" },
];

const STRATEGY_OPTIONS = [
  { value: "dca", label: "DCA", icon: "📅" },
  { value: "hold", label: "Hold", icon: "💎" },
  { value: "swing", label: "Swing", icon: "🌊" },
  { value: "day_trading", label: "Day Trading", icon: "⚡" },
  { value: "scalping", label: "Scalping", icon: "🎯" },
  { value: "position", label: "Position", icon: "🏛️" },
];

const GOAL_OPTIONS = [
  { value: "growth", label: "Crecimiento", icon: "📈" },
  { value: "income", label: "Ingresos", icon: "💰" },
  { value: "preservation", label: "Preservación", icon: "🛡️" },
  { value: "speculation", label: "Especulación", icon: "🎲" },
];

function ProfileChip({
  selected,
  onClick,
  icon,
  label,
}: {
  selected: boolean;
  onClick: () => void;
  icon?: string;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 h-8 rounded-[8px] border text-[12px] font-bold transition-all",
        selected
          ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
          : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]/40"
      )}
    >
      {icon && <span>{icon}</span>}
      {label}
      {selected && <Check size={12} />}
    </button>
  );
}

export function PreferencesPage() {
  const { theme, toggleTheme } = useTheme();
  const { supportedBrokers, connectedAccounts } = useBrokerContext();

  const [_profile, setProfile] = useState<UserProfileData | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);

  // Editable local state
  const [experience, setExperience] = useState("");
  const [risk, setRisk] = useState("");
  const [assets, setAssets] = useState<string[]>([]);
  const [capital, setCapital] = useState("");
  const [strategies, setStrategies] = useState<string[]>([]);
  const [goal, setGoal] = useState("");

  useEffect(() => {
    (async () => {
      const p = await getUserProfile();
      setProfile(p);
      if (p && p.onboarding_completed) {
        setExperience(p.experience_level || "");
        setRisk(p.risk_tolerance || "");
        setAssets(p.asset_interests || []);
        setCapital(p.capital_range || "");
        setStrategies(p.preferred_strategies || []);
        setGoal(p.trading_goal || "");
      }
      setProfileLoading(false);
    })();
  }, []);

  const toggleArray = (arr: string[], val: string, setter: (v: string[]) => void) => {
    setter(arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]);
  };

  const handleSave = async () => {
    setSaving(true);
    const updated = await saveUserProfile({
      experience_level: experience,
      risk_tolerance: risk,
      asset_interests: assets,
      capital_range: capital,
      preferred_strategies: strategies,
      trading_goal: goal,
      preferred_language: "es",
    });
    setSaving(false);
    if (updated) {
      setProfile(updated);
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2000);
    }
  };

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

      {/* Trading Profile */}
      <div className="panel p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Rocket size={18} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Perfil de Trading</h3>
        </div>

        {profileLoading ? (
          <div className="h-32 bg-[var(--color-surface-2)] rounded animate-pulse" />
        ) : (
          <>
            {/* Experience */}
            <div>
              <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1">
                <Rocket size={11} /> Experiencia
              </p>
              <div className="flex flex-wrap gap-2">
                {EXPERIENCE_OPTIONS.map((opt) => (
                  <ProfileChip key={opt.value} selected={experience === opt.value} onClick={() => setExperience(opt.value)} icon={opt.icon} label={opt.label} />
                ))}
              </div>
            </div>

            {/* Risk */}
            <div>
              <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1">
                <Shield size={11} /> Tolerancia al riesgo
              </p>
              <div className="flex flex-wrap gap-2">
                {RISK_OPTIONS.map((opt) => (
                  <ProfileChip key={opt.value} selected={risk === opt.value} onClick={() => setRisk(opt.value)} icon={opt.icon} label={opt.label} />
                ))}
              </div>
            </div>

            {/* Assets */}
            <div>
              <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1">
                <Target size={11} /> Mercados de interés
              </p>
              <div className="flex flex-wrap gap-2">
                {ASSET_OPTIONS.map((opt) => (
                  <ProfileChip key={opt.value} selected={assets.includes(opt.value)} onClick={() => toggleArray(assets, opt.value, setAssets)} icon={opt.icon} label={opt.label} />
                ))}
              </div>
            </div>

            {/* Capital */}
            <div>
              <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1">
                <Wallet size={11} /> Capital
              </p>
              <div className="flex flex-wrap gap-2">
                {CAPITAL_OPTIONS.map((opt) => (
                  <ProfileChip key={opt.value} selected={capital === opt.value} onClick={() => setCapital(opt.value)} label={opt.label} />
                ))}
              </div>
            </div>

            {/* Strategies */}
            <div>
              <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1">
                <Target size={11} /> Estrategias preferidas
              </p>
              <div className="flex flex-wrap gap-2">
                {STRATEGY_OPTIONS.map((opt) => (
                  <ProfileChip key={opt.value} selected={strategies.includes(opt.value)} onClick={() => toggleArray(strategies, opt.value, setStrategies)} icon={opt.icon} label={opt.label} />
                ))}
              </div>
            </div>

            {/* Goal */}
            <div>
              <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2 flex items-center gap-1">
                <Check size={11} /> Objetivo
              </p>
              <div className="flex flex-wrap gap-2">
                {GOAL_OPTIONS.map((opt) => (
                  <ProfileChip key={opt.value} selected={goal === opt.value} onClick={() => setGoal(opt.value)} icon={opt.icon} label={opt.label} />
                ))}
              </div>
            </div>

            {/* Save button */}
            <div className="flex items-center gap-3 pt-2">
              <Button variant="primary" size="sm" onClick={handleSave} disabled={saving}>
                {saving ? "Guardando..." : "Guardar perfil"}
              </Button>
              {savedMsg && (
                <span className="text-[12px] font-bold text-[var(--color-success)] flex items-center gap-1">
                  <Check size={14} /> Guardado
                </span>
              )}
            </div>
          </>
        )}
      </div>

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
            defaultValue={localStorage.getItem("aiServerUrl") || "http://76.13.180.80:8001"}
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
