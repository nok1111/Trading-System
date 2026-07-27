import { useState } from "react";
import { Rocket, TrendingUp, Shield, Wallet, Target, Check, ChevronRight, ChevronLeft } from "lucide-react";
import { cn } from "../../lib/utils";
import { saveUserProfile, type UserProfileData } from "../../lib/intelligenceApi";

interface OnboardingModalProps {
  onComplete: (profile: UserProfileData) => void;
}

const STEPS = [
  "experience",
  "risk",
  "assets",
  "capital",
  "strategies",
  "goal",
] as const;

type Step = (typeof STEPS)[number];

const EXPERIENCE_OPTIONS = [
  { value: "beginner", label: "Principiante", desc: "Nuevo en trading, quiero aprender", icon: "🌱" },
  { value: "intermediate", label: "Intermedio", desc: "Ya he operado, conozco lo básico", icon: "📈" },
  { value: "advanced", label: "Avanzado", desc: "Trader activo, análisis técnico avanzado", icon: "🚀" },
];

const RISK_OPTIONS = [
  { value: "conservative", label: "Conservador", desc: "Prefiero seguridad, ganancias estables", icon: "🛡️" },
  { value: "moderate", label: "Moderado", desc: "Balance entre riesgo y recompensa", icon: "⚖️" },
  { value: "aggressive", label: "Agresivo", desc: "Busco máximas ganancias, alto riesgo", icon: "🔥" },
];

const ASSET_OPTIONS = [
  { value: "crypto", label: "Criptomonedas", icon: "₿" },
  { value: "stocks", label: "Acciones", icon: "📊" },
  { value: "forex", label: "Forex", icon: "💱" },
  { value: "commodities", label: "Oro / Commodities", icon: "🥇" },
];

const CAPITAL_OPTIONS = [
  { value: "<100", label: "Menos de $100" },
  { value: "100-1000", label: "$100 - $1,000" },
  { value: "1000-10000", label: "$1,000 - $10,000" },
  { value: "10000-50000", label: "$10,000 - $50,000" },
  { value: "50000+", label: "Más de $50,000" },
];

const STRATEGY_OPTIONS = [
  { value: "dca", label: "DCA", desc: "Compras programadas y regulares", icon: "📅" },
  { value: "hold", label: "Hold", desc: "Comprar y mantener a largo plazo", icon: "💎" },
  { value: "swing", label: "Swing Trading", desc: "Operas de días a semanas", icon: "🌊" },
  { value: "day_trading", label: "Day Trading", desc: "Operas dentro del día", icon: "⚡" },
  { value: "scalping", label: "Scalping", desc: "Operaciones de minutos", icon: "🎯" },
  { value: "position", label: "Position Trading", desc: "Operas de meses a años", icon: "🏛️" },
];

const GOAL_OPTIONS = [
  { value: "growth", label: "Crecimiento", desc: "Aumentar mi capital con el tiempo", icon: "📈" },
  { value: "income", label: "Ingresos", desc: "Generar ingresos regulares", icon: "💰" },
  { value: "preservation", label: "Preservación", desc: "Proteger mi capital de la inflación", icon: "🛡️" },
  { value: "speculation", label: "Especulación", desc: "Altas ganancias en corto plazo", icon: "🎲" },
];

export function OnboardingModal({ onComplete }: OnboardingModalProps) {
  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState("");
  const [risk, setRisk] = useState("");
  const [assets, setAssets] = useState<string[]>([]);
  const [capital, setCapital] = useState("");
  const [strategies, setStrategies] = useState<string[]>([]);
  const [goal, setGoal] = useState("");
  const [saving, setSaving] = useState(false);

  const currentStep = STEPS[step];
  const isLastStep = step === STEPS.length - 1;
  const canProceed = (() => {
    switch (currentStep) {
      case "experience": return !!experience;
      case "risk": return !!risk;
      case "assets": return assets.length > 0;
      case "capital": return !!capital;
      case "strategies": return strategies.length > 0;
      case "goal": return !!goal;
    }
  })();

  const toggleArray = (arr: string[], val: string, setter: (v: string[]) => void) => {
    setter(arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]);
  };

  const handleFinish = async () => {
    setSaving(true);
    const profile = await saveUserProfile({
      experience_level: experience,
      risk_tolerance: risk,
      asset_interests: assets,
      capital_range: capital,
      preferred_strategies: strategies,
      trading_goal: goal,
      preferred_language: "es",
    });
    setSaving(false);
    if (profile) {
      onComplete(profile);
    }
  };

  const stepIcons: Record<Step, typeof Rocket> = {
    experience: Rocket,
    risk: Shield,
    assets: TrendingUp,
    capital: Wallet,
    strategies: Target,
    goal: Check,
  };

  const Icon = stepIcons[currentStep];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-[560px] mx-4 rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-full bg-[var(--color-primary)]/10 flex items-center justify-center">
              <Icon size={20} className="text-[var(--color-primary)]" />
            </div>
            <div>
              <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">
                Bienvenido a tu Dashboard
              </h2>
              <p className="text-[12px] text-[var(--color-text-muted)]">
                Personalizamos tu experiencia en {STEPS.length} pasos · Paso {step + 1} de {STEPS.length}
              </p>
            </div>
          </div>
          {/* Progress bar */}
          <div className="flex gap-1 mt-3">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={cn(
                  "h-1.5 flex-1 rounded-full transition-colors",
                  i <= step ? "bg-[var(--color-primary)]" : "bg-[var(--color-surface-2)]"
                )}
              />
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5 min-h-[280px]">
          {currentStep === "experience" && (
            <div className="space-y-2">
              <p className="text-[14px] font-bold text-[var(--color-text)] mb-3">¿Cuál es tu nivel de experiencia?</p>
              {EXPERIENCE_OPTIONS.map((opt) => (
                <OptionCard
                  key={opt.value}
                  selected={experience === opt.value}
                  onClick={() => setExperience(opt.value)}
                  icon={opt.icon}
                  label={opt.label}
                  desc={opt.desc}
                />
              ))}
            </div>
          )}

          {currentStep === "risk" && (
            <div className="space-y-2">
              <p className="text-[14px] font-bold text-[var(--color-text)] mb-3">¿Cuál es tu tolerancia al riesgo?</p>
              {RISK_OPTIONS.map((opt) => (
                <OptionCard
                  key={opt.value}
                  selected={risk === opt.value}
                  onClick={() => setRisk(opt.value)}
                  icon={opt.icon}
                  label={opt.label}
                  desc={opt.desc}
                />
              ))}
            </div>
          )}

          {currentStep === "assets" && (
            <div>
              <p className="text-[14px] font-bold text-[var(--color-text)] mb-3">¿En qué mercados estás interesado?</p>
              <p className="text-[11px] text-[var(--color-text-muted)] mb-3">Selecciona todos los que apliquen</p>
              <div className="grid grid-cols-2 gap-2">
                {ASSET_OPTIONS.map((opt) => (
                  <MultiOptionCard
                    key={opt.value}
                    selected={assets.includes(opt.value)}
                    onClick={() => toggleArray(assets, opt.value, setAssets)}
                    icon={opt.icon}
                    label={opt.label}
                  />
                ))}
              </div>
            </div>
          )}

          {currentStep === "capital" && (
            <div className="space-y-2">
              <p className="text-[14px] font-bold text-[var(--color-text)] mb-3">¿Cuánto capital planeas invertir?</p>
              {CAPITAL_OPTIONS.map((opt) => (
                <OptionCard
                  key={opt.value}
                  selected={capital === opt.value}
                  onClick={() => setCapital(opt.value)}
                  label={opt.label}
                />
              ))}
            </div>
          )}

          {currentStep === "strategies" && (
            <div>
              <p className="text-[14px] font-bold text-[var(--color-text)] mb-3">¿Qué estrategias prefieres?</p>
              <p className="text-[11px] text-[var(--color-text-muted)] mb-3">Selecciona todas las que te interesen</p>
              <div className="grid grid-cols-2 gap-2">
                {STRATEGY_OPTIONS.map((opt) => (
                  <MultiOptionCard
                    key={opt.value}
                    selected={strategies.includes(opt.value)}
                    onClick={() => toggleArray(strategies, opt.value, setStrategies)}
                    icon={opt.icon}
                    label={opt.label}
                    desc={opt.desc}
                  />
                ))}
              </div>
            </div>
          )}

          {currentStep === "goal" && (
            <div className="space-y-2">
              <p className="text-[14px] font-bold text-[var(--color-text)] mb-3">¿Cuál es tu objetivo principal?</p>
              {GOAL_OPTIONS.map((opt) => (
                <OptionCard
                  key={opt.value}
                  selected={goal === opt.value}
                  onClick={() => setGoal(opt.value)}
                  icon={opt.icon}
                  label={opt.label}
                  desc={opt.desc}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--color-border)] flex items-center justify-between">
          <button
            onClick={() => step > 0 && setStep(step - 1)}
            disabled={step === 0}
            className={cn(
              "flex items-center gap-1 px-3 h-9 rounded-[8px] text-[12px] font-bold transition-colors",
              step === 0
                ? "text-[var(--color-text-muted)] opacity-40 cursor-not-allowed"
                : "text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
            )}
          >
            <ChevronLeft size={14} />
            Atrás
          </button>

          {isLastStep ? (
            <button
              onClick={handleFinish}
              disabled={!canProceed || saving}
              className={cn(
                "flex items-center gap-1.5 px-5 h-9 rounded-[8px] text-[13px] font-bold transition-colors",
                canProceed && !saving
                  ? "bg-[var(--color-primary)] text-white hover:opacity-90"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
              )}
            >
              {saving ? "Guardando..." : "Comenzar"}
              {!saving && <Check size={14} />}
            </button>
          ) : (
            <button
              onClick={() => canProceed && setStep(step + 1)}
              disabled={!canProceed}
              className={cn(
                "flex items-center gap-1 px-5 h-9 rounded-[8px] text-[13px] font-bold transition-colors",
                canProceed
                  ? "bg-[var(--color-primary)] text-white hover:opacity-90"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
              )}
            >
              Siguiente
              <ChevronRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function OptionCard({
  selected,
  onClick,
  icon,
  label,
  desc,
}: {
  selected: boolean;
  onClick: () => void;
  icon?: string;
  label: string;
  desc?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 p-3 rounded-[10px] border text-left transition-all",
        selected
          ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
          : "border-[var(--color-border)] hover:border-[var(--color-primary)]/40 hover:bg-[var(--color-surface-2)]"
      )}
    >
      {icon && <span className="text-[20px]">{icon}</span>}
      <div className="flex-1">
        <p className={cn("text-[13px] font-bold", selected ? "text-[var(--color-primary)]" : "text-[var(--color-text)]")}>
          {label}
        </p>
        {desc && <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{desc}</p>}
      </div>
      {selected && (
        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)] flex items-center justify-center shrink-0">
          <Check size={12} className="text-white" />
        </div>
      )}
    </button>
  );
}

function MultiOptionCard({
  selected,
  onClick,
  icon,
  label,
  desc,
}: {
  selected: boolean;
  onClick: () => void;
  icon?: string;
  label: string;
  desc?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col items-start gap-1 p-3 rounded-[10px] border text-left transition-all",
        selected
          ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
          : "border-[var(--color-border)] hover:border-[var(--color-primary)]/40 hover:bg-[var(--color-surface-2)]"
      )}
    >
      <div className="flex items-center gap-2 w-full">
        {icon && <span className="text-[16px]">{icon}</span>}
        <p className={cn("text-[12px] font-bold flex-1", selected ? "text-[var(--color-primary)]" : "text-[var(--color-text)]")}>
          {label}
        </p>
        {selected && (
          <div className="w-4 h-4 rounded-full bg-[var(--color-primary)] flex items-center justify-center shrink-0">
            <Check size={10} className="text-white" />
          </div>
        )}
      </div>
      {desc && <p className="text-[10px] text-[var(--color-text-muted)]">{desc}</p>}
    </button>
  );
}
