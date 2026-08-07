import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { toast } from "../components/ui/Toast";
import { cn } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { Tooltip } from "../components/common/Tooltip";

const PROVIDERS = [
  { value: "gemini", label: "Gemini (Google Cloud) - Gratis" },
  { value: "groq", label: "Groq (Cloud) - Gratis" },
  { value: "ollama", label: "Ollama (Local) - Gratis" },
  { value: "openai", label: "OpenAI (GPT-4o) - Premium", premium: true },
  { value: "deepseek", label: "DeepSeek - Premium", premium: true },
  { value: "mistral", label: "Mistral AI - Premium", premium: true },
];

const MODELS: Record<string, { value: string; label: string }[]> = {
  gemini: [
    { value: "gemini-flash-latest", label: "Gemini Flash Latest (recomendado)" },
    { value: "gemini-flash-lite-latest", label: "Gemini Flash Lite Latest" },
    { value: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
    { value: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite" },
  ],
  groq: [
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant" },
  ],
  ollama: [
    { value: "qwen2.5:14b", label: "Qwen 2.5 14B" },
    { value: "qwen2.5:7b", label: "Qwen 2.5 7B (rapido)" },
    { value: "llama3.2:3b", label: "Llama 3.2 3B" },
  ],
  openai: [
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  ],
  deepseek: [
    { value: "deepseek-chat", label: "DeepSeek Chat (V3)" },
    { value: "deepseek-reasoner", label: "DeepSeek Reasoner (R1)" },
  ],
  mistral: [
    { value: "mistral-large-latest", label: "Mistral Large" },
    { value: "mistral-small-latest", label: "Mistral Small" },
  ],
};

export function AIAgentPage() {
  const [status, setStatus] = useState<any>(null);
  const [log, setLog] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-flash-latest");
  const [interval, setIntervalVal] = useState(30);
  const [tradeMode, setTradeMode] = useState<"paper" | "live">("paper");
  const [autoTrade, setAutoTrade] = useState(true);
  const [groqKey, setGroqKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [premiumKey, setPremiumKey] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [aiMode, setAiMode] = useState<"conservative" | "balanced" | "aggressive">("balanced");
  const [showConfig, setShowConfig] = useState(false);
  const [plan, setPlan] = useState<any>(null);
  const [brokers, setBrokers] = useState<any[]>([]);
  const [selectedBroker, setSelectedBroker] = useState<string>("paper");
  const [brokerBalance, setBrokerBalance] = useState<any>(null);
  const [allocatedCapital, setAllocatedCapital] = useState<number>(0);
  const [capitalInput, setCapitalInput] = useState<string>("");
  // Nivel 1: Symbol controls + feature toggles
  const [whitelist, setWhitelist] = useState("");
  const [blacklist, setBlacklist] = useState("");
  const [useRegime, setUseRegime] = useState(true);
  const [useMtf, setUseMtf] = useState(true);
  const [useCorrelation, setUseCorrelation] = useState(true);
  // Nivel 2: Performance learning
  const [perfData, setPerfData] = useState<any>(null);
  // Nivel 3: Custom instructions + backtest comparison
  const [customInstructions, setCustomInstructions] = useState("");
  const [backtestData, setBacktestData] = useState<any>(null);
  const [backtestDays, setBacktestDays] = useState(30);

  const loadStatus = useCallback(async () => {
    try {
      const s = await api<any>("/api/ai-agent/status");
      setStatus(s);
    } catch {}
  }, []);

  const loadLog = useCallback(async () => {
    try {
      const l = await api<any[]>("/api/ai-agent/log?limit=100");
      setLog(l);
    } catch {}
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const s = await api<any>("/api/ai-agent/stats");
      setStats(s);
    } catch {}
  }, []);

  const loadPlan = useCallback(async () => {
    try {
      const p = await api<any>("/api/ai-agent/plan");
      setPlan(p);
    } catch {}
  }, []);

  const loadBrokers = useCallback(async () => {
    try {
      const r = await api<any>("/api/ai-agent/brokers");
      setBrokers(r.brokers || []);
      setSelectedBroker(r.current || "paper");
    } catch {}
  }, []);

  const loadBrokerBalance = useCallback(async () => {
    if (selectedBroker === "paper" || selectedBroker === "mock") { setBrokerBalance(null); return; }
    try {
      const r = await api<any>(`/api/broker/${selectedBroker}/balance`);
      setBrokerBalance(r);
    } catch { setBrokerBalance(null); }
  }, [selectedBroker]);

  const loadTradingMode = useCallback(async () => {
    try {
      const r = await api<any>("/api/trading-mode");
      setAllocatedCapital(r.allocated_capital || 0);
    } catch {}
  }, []);

  const loadSymbolSettings = useCallback(async () => {
    try {
      const r = await api<any>("/api/ai-agent/symbol-settings");
      setWhitelist(r.whitelist || "");
      setBlacklist(r.blacklist || "");
      setUseRegime(r.use_market_regime ?? true);
      setUseMtf(r.use_mtf_confirm ?? true);
      setUseCorrelation(r.use_correlation_filter ?? true);
      setCustomInstructions(r.custom_instructions || "");
    } catch {}
  }, []);

  const loadPerfData = useCallback(async () => {
    try {
      const r = await api<any>("/api/ai-agent/performance-learning");
      setPerfData(r);
    } catch {}
  }, []);

  const loadBacktest = useCallback(async () => {
    try {
      const r = await api<any>(`/api/ai-agent/backtest-comparison?days=${backtestDays}`);
      setBacktestData(r);
    } catch {}
  }, [backtestDays]);

  const saveSymbolSettings = async () => {
    try {
      await api("/api/ai-agent/symbol-settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          whitelist,
          blacklist,
          use_market_regime: useRegime,
          use_mtf_confirm: useMtf,
          use_correlation_filter: useCorrelation,
          custom_instructions: customInstructions,
        }),
      });
      toast("Configuración guardada");
    } catch (e: any) {
      toast(e.message || "Error al guardar", false);
    }
  };

  useEffect(() => {
    loadStatus();
    loadLog();
    loadStats();
    loadPlan();
    loadBrokers();
    loadTradingMode();
    loadSymbolSettings();
    loadPerfData();
    loadBacktest();
    const id1 = setInterval(loadStatus, 5000);
    const id2 = setInterval(loadLog, 5000);
    const id3 = setInterval(loadStats, 15000);
    const id4 = setInterval(loadPerfData, 60000);
    return () => {
      clearInterval(id1);
      clearInterval(id2);
      clearInterval(id3);
      clearInterval(id4);
    };
  }, [loadStatus, loadLog, loadStats, loadPlan, loadBrokers, loadTradingMode, loadSymbolSettings, loadPerfData, loadBacktest]);

  useEffect(() => {
    loadBrokerBalance();
    const id = setInterval(loadBrokerBalance, 30000);
    return () => clearInterval(id);
  }, [loadBrokerBalance]);

  const start = async () => {
    try {
      const body: any = {
        provider,
        model,
        interval_seconds: interval,
        auto_trade: autoTrade,
        trade_mode: tradeMode,
      };
      if (groqKey) body.groq_api_key = groqKey;
      if (geminiKey) body.gemini_api_key = geminiKey;
      if (premiumKey) body.premium_api_key = premiumKey;

      await api("/api/ai-agent/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      toast("AI Agent activado");
      loadStatus();
      loadPlan();
    } catch (e: any) {
      const msg = e?.message || "Error al iniciar";
      toast(msg, false);
    }
  };

  const stop = async () => {
    try {
      await api("/api/ai-agent/stop", { method: "POST" });
      toast("AI Agent desactivado");
      loadStatus();
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const testKey = async () => {
    setTestResult("Probando...");
    try {
      const body: any = { provider, model };
      if (groqKey) body.groq_api_key = groqKey;
      if (geminiKey) body.gemini_api_key = geminiKey;
      if (premiumKey) body.premium_api_key = premiumKey;

      const r = await api<any>("/api/ai-agent/test-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setTestResult(r.ok ? "✓ API Key valida" : "✗ " + (r.error || "API Key invalida"));
      toast(r.ok ? "API Key valida" : (r.error || "API Key invalida"), r.ok);
    } catch (e: any) {
      setTestResult("✗ Error: " + e.message);
      toast(e.message, false);
    }
  };

  const setIntervalApi = async () => {
    try {
      await api(`/api/ai-agent/interval?interval_seconds=${interval}`, { method: "PATCH" });
      toast("Intervalo actualizado");
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const toggleAutoTrade = async () => {
    const newVal = !autoTrade;
    setAutoTrade(newVal);
    try {
      await api(`/api/ai-agent/auto-trade?enabled=${newVal}`, { method: "PATCH" });
      toast(`Auto-trade ${newVal ? "activado" : "desactivado"}`);
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const selectBroker = async (brokerId: string) => {
    try {
      await api(`/api/ai-agent/broker?broker_id=${brokerId}`, { method: "PATCH" });
      setSelectedBroker(brokerId);
      toast(`Broker cambiado a ${brokerId}`);
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const assignCapital = async () => {
    const amount = parseFloat(capitalInput) || 0;
    try {
      const r = await api<any>(`/api/ai-agent/capital?amount=${amount}`, { method: "PATCH" });
      setAllocatedCapital(amount);
      setCapitalInput("");
      toast(r.message || `Capital asignado: $${amount}`);
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const useAllBalance = async () => {
    try {
      const r = await api<any>(`/api/ai-agent/capital?amount=0`, { method: "PATCH" });
      setAllocatedCapital(0);
      toast(r.message || "Usando todo el saldo disponible");
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const isRunning = status?.is_running ?? false;
  const decisions = log.filter((e) => e.phase === "decision");
  const activityLog = log.slice(0, 60);

  // Restore saved provider and model from user's last session (only when agent is stopped)
  useEffect(() => {
    if (!isRunning && status?.saved_provider) {
      setProvider(status.saved_provider);
    }
    if (!isRunning && status?.saved_model) {
      setModel(status.saved_model);
    }
  }, [status?.saved_provider, status?.saved_model, isRunning]);

  // Plan info
  const isFree = plan?.is_free ?? true;
  const isPaid = plan?.is_paid ?? false;
  const subscription = plan?.subscription ?? "free";
  const hasGroqKey = plan?.has_groq_key ?? false;
  const hasGeminiKey = plan?.has_gemini_key ?? false;
  const hasPremiumKey = plan?.has_premium_key ?? false;
  const maxRequestsPerDay = plan?.max_ai_requests_per_day ?? 50;
  const minInterval = plan?.min_interval_seconds ?? 120;
  const isPremiumProvider = PROVIDERS.find((p) => p.value === provider)?.premium ?? false;
  const needsByok = isFree && (provider === "groq" || provider === "gemini");
  const byokReady = (provider === "groq" && (hasGroqKey || !!groqKey)) || (provider === "gemini" && (hasGeminiKey || !!geminiKey));
  const canStart = !isRunning && (!needsByok || byokReady) && (!isPremiumProvider || isPaid);
  const totalTrades = stats?.total_trades ?? 0;
  const winRate = stats?.win_rate ?? 0;
  const totalPnl = stats?.total_pnl ?? 0;
  const openPositions = stats?.open_positions ?? 0;
  const wins = stats?.wins ?? 0;
  const losses = stats?.losses ?? 0;
  const cycles = status?.cycles ?? 0;
  const decisionsWithActions = stats?.decisions_with_actions ?? 0;
  const decisionsHold = stats?.decisions_hold ?? 0;
  const pnlSeries = stats?.pnl_series ?? [];
  const cumulativePnl: number[] = [];
  let runningPnl = 0;
  for (const p of [...pnlSeries].reverse()) {
    if (p.side === "SELL") runningPnl += p.realized_pnl;
    cumulativePnl.push(runningPnl);
  }

  return (
    <div className="p-5 space-y-4 max-w-[1200px] mx-auto">
      {/* Hero card - que es, estado, controles principales */}
      <Card className="border-l-4 border-l-[var(--color-accent)]">
        <div className="flex justify-between items-start flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-12 h-12 rounded-[12px] flex items-center justify-center text-[24px]",
              isRunning ? "bg-[var(--color-success)]/15" : "bg-[var(--color-surface-2)]"
            )}>
              {isRunning ? "🤖" : "💤"}
            </div>
            <div>
              <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">Asistente de Trading con IA</h2>
              <p className="text-[12px] text-[var(--color-text-muted)]">
                {isRunning ? (
                  <>
                    <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] mr-1.5 animate-pulse" />
                    Analizando mercado ? Ciclo {cycles} ? {status?.model || "IA"}
                  </>
                ) : (
                  "Detenido - clic en Activar para empezar"
                )}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Tooltip text="Inicia el asistente. Analiza el mercado y genera señales de compra/venta automáticamente.">
              <Button variant="success" onClick={start} disabled={!canStart || isRunning} className="h-9">▶ Activar</Button>
            </Tooltip>
            <Tooltip text="Detiene el asistente. Las posiciones abiertas se mantienen hasta SL/TP.">
              <Button variant="danger" onClick={stop} disabled={!isRunning} className="h-9">⏹ Detener</Button>
            </Tooltip>
            <Tooltip text="Muestra u oculta opciones avanzadas: proveedor de IA, API key, intervalo.">
              <Button variant="default" onClick={() => setShowConfig(!showConfig)} disabled={isRunning} className="h-9">⚙ Avanzado</Button>
            </Tooltip>
          </div>
        </div>

        {/* ¿Qué es esto - explicación clara para principiantes */}
        <div className="mt-4 rounded-[10px] bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/15 p-4">
          <p className="text-[12px] text-[var(--color-text)] leading-relaxed">
            <strong>¿Qué hace?</strong> El asistente analiza el mercado de criptomonedas cada {interval} segundos usando inteligencia artificial.
            Cuando detecta una oportunidad de compra o venta, te avisa y -si tu lo permites- ejecuta la operación automáticamente con stop loss y take profit para proteger tu capital.
          </p>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-2">
            Solo opera criptomonedas (no stocks). Nunca opera con más capital del que tu permitas.
          </p>
        </div>

        {/* Plan badge + quota info */}
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <span className={cn(
            "text-[10px] font-bold px-2.5 h-6 rounded-full flex items-center uppercase tracking-wide",
            isPaid
              ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          )}>
            {isPaid ? "⭐ " : ""}{subscription}
          </span>
          <span className="text-[11px] text-[var(--color-text-muted)]">
            {maxRequestsPerDay === 99999 ? "Ilimitado" : `${maxRequestsPerDay} análisis/día`} ? min intervalo {minInterval}s
          </span>
        </div>

        {/* BYOK notice for FREE users with free providers */}
        {needsByok && !byokReady && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30">
            <p className="text-[12px] font-bold text-[var(--color-warning)]">
              🔑 Necesitas una API key gratuita para usar este proveedor de IA
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              {provider === "groq" ? (
                <>Obtén una key gratis en <a href="https://console.groq.com/keys" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline">console.groq.com/keys</a> y pégala en Opciones Avanzadas abajo.</>
              ) : (
                <>Obtén una key gratis en <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline">aistudio.google.com/apikey</a> y pégala en Opciones Avanzadas abajo.</>
              )}
            </p>
          </div>
        )}

        {/* Premium provider locked for FREE */}
        {isPremiumProvider && isFree && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
            <p className="text-[12px] font-bold text-[var(--color-danger)]">
              🔒 {provider} requiere suscripción PRO o PREMIUM
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              Mejora tu plan para usar proveedores de IA premium, o usa Groq/Gemini (gratis) con tu propia key.
            </p>
          </div>
        )}

        {/* --- Paso 1: Modo de operación --- */}
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[10px] font-bold flex items-center justify-center">1</span>
            <span className="text-[12px] font-bold text-[var(--color-text)]">¿Cómo quieres operar?</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => !isRunning && setTradeMode("paper")}
              disabled={isRunning}
              className={cn(
                "rounded-[10px] p-3 text-left border transition-all",
                tradeMode === "paper"
                  ? "bg-[var(--color-success)]/10 border-[var(--color-success)]/40"
                  : "bg-[var(--color-surface-2)] border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]"
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[16px]">🎯</span>
                <span className={cn("text-[13px] font-extrabold", tradeMode === "paper" ? "text-[var(--color-success)]" : "text-[var(--color-text)]")}>
                  Practica (sin dinero real)
                </span>
              </div>
              <p className="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
                La IA simula operaciones con dinero ficticio. Ideal para aprender y probar sin riesgo. <strong>Recomendado para principiantes.</strong>
              </p>
            </button>
            <button
              onClick={() => !isRunning && setTradeMode("live")}
              disabled={isRunning}
              className={cn(
                "rounded-[10px] p-3 text-left border transition-all",
                tradeMode === "live"
                  ? "bg-[var(--color-danger)]/10 border-[var(--color-danger)]/40"
                  : "bg-[var(--color-surface-2)] border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]"
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[16px]">💰</span>
                <span className={cn("text-[13px] font-extrabold", tradeMode === "live" ? "text-[var(--color-danger)]" : "text-[var(--color-text)]")}>
                  Dinero Real
                </span>
              </div>
              <p className="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
                La IA ejecuta operaciones reales en tu cuenta del broker. <strong>Puedes ganar o perder dinero real.</strong> Solo para usuarios con experiencia.
              </p>
            </button>
          </div>
          {tradeMode === "live" && (
            <div className="mt-2 p-2.5 rounded-[8px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
              <p className="text-[11px] font-bold text-[var(--color-danger)]">
                ⚠️ Modo Dinero Real activado. La IA usará tu saldo del broker para comprar y vender.
              </p>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                Puedes limitar cuanto dinero usa en la seccion "Presupuesto" abajo. La IA nunca usará más de lo que tu permitas.
              </p>
            </div>
          )}
        </div>

        {/* --- Paso 2: Estilo de trading --- */}
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[10px] font-bold flex items-center justify-center">2</span>
            <span className="text-[12px] font-bold text-[var(--color-text)]">¿Qué tan agresivo quieres que sea?</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {([
              { value: "conservative", label: "Cauteloso", desc: "Menos operaciones, stops ajustados. Prioriza proteger tu capital.", icon: "🛡️" },
              { value: "balanced", label: "Balanceado", desc: "Mezcla de operaciones seguras y oportunidades. Recomendado.", icon: "⚖️" },
              { value: "aggressive", label: "Agresivo", desc: "Más operaciones, stops amplios. Busca maximizar ganancias pero con más riesgo.", icon: "🚀" },
            ] as const).map((m) => (
              <button
                key={m.value}
                onClick={() => !isRunning && setAiMode(m.value)}
                disabled={isRunning}
                className={cn(
                  "rounded-[10px] p-3 text-center border transition-all",
                  aiMode === m.value
                    ? "bg-[var(--color-accent)]/15 border-[var(--color-accent)] text-[var(--color-accent)]"
                    : "bg-[var(--color-surface-2)] border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
                )}
              >
                <div className="text-[20px] mb-1">{m.icon}</div>
                <div className="text-[12px] font-bold">{m.label}</div>
                <div className="text-[9px] mt-1 leading-tight opacity-80">{m.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* --- Paso 3: Ejecucion automática --- */}
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[10px] font-bold flex items-center justify-center">3</span>
            <span className="text-[12px] font-bold text-[var(--color-text)]">¿Quieres que la IA ejecute operaciones sola?</span>
          </div>
          <div className="rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-3">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-[12px] font-bold text-[var(--color-text)]">
                  Ejecucion automática {autoTrade ? "(Activada)" : "(Desactivada)"}
                </p>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1 leading-relaxed">
                  {autoTrade ? (
                    <>
                      ✅ La IA comprará y venderá automáticamente cuando detecte oportunidades.<br />
                      <span className="text-[var(--color-warning)]">Solo usará el dinero que le asignes en el Presupuesto.</span>
                    </>
                  ) : (
                    <>
                      ⏸️ La IA solo te mostrará señales de compra/venta. <strong>Tu decides</strong> si ejecutarlas manualmente.
                    </>
                  )}
                </p>
              </div>
              <label className="flex items-center gap-2 cursor-pointer ml-3">
                <input type="checkbox" checked={autoTrade} onChange={toggleAutoTrade} disabled={isRunning} className="w-5 h-5 accent-[var(--color-accent)]" />
              </label>
            </div>
            {autoTrade && tradeMode === "live" && (
              <div className="mt-2 p-2 rounded-[6px] bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/20">
                <p className="text-[10px] text-[var(--color-warning)] font-bold">
                  ⚠️ La IA operará con dinero real automáticamente. Asegúrate de haber configurado un presupuesto límite.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* --- Paso 4: Broker (solo si live) --- */}
        {tradeMode === "live" && (
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[10px] font-bold flex items-center justify-center">4</span>
              <span className="text-[12px] font-bold text-[var(--color-text)]">¿En qué exchange tienes tu cuenta?</span>
            </div>
            <div className="flex gap-2 flex-wrap">
              {brokers.filter((b) => b.id !== "paper").map((b) => {
                const isSelected = selectedBroker === b.id;
                const isDisabled = !b.implemented;
                const brokerColors: Record<string, string> = {
                  binance: "#F0B90B",
                  bybit: "#F7A600",
                  coinbase: "#0052FF",
                  kraken: "#5841D8",
                  okx: "#000000",
                };
                const color = brokerColors[b.id] || "var(--color-accent)";
                return (
                  <button
                    key={b.id}
                    onClick={() => !isDisabled && !isRunning && selectBroker(b.id)}
                    disabled={isDisabled || isRunning}
                    className={cn(
                      "px-3 h-9 rounded-[8px] text-[12px] font-bold transition-all border flex items-center gap-2",
                      isSelected
                        ? "text-white"
                        : isDisabled
                          ? "bg-[var(--color-surface-2)] border-[var(--color-border)] text-[var(--color-text-muted)] opacity-50 cursor-not-allowed"
                          : !b.connected
                            ? "bg-[var(--color-surface-2)] border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
                            : "bg-[var(--color-surface-2)] border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                    )}
                    style={isSelected ? { backgroundColor: color, borderColor: color } : {}}
                    title={
                      isDisabled
                        ? "Proximamente"
                        : !b.connected
                          ? "Conecta tu cuenta en la pagina Connections primero"
                          : b.name
                    }
                  >
                    {b.id === "binance" && "🟡"}
                    {b.id === "bybit" && "🟠"}
                    {b.id === "coinbase" && "🔵"}
                    {b.id === "kraken" && "🟣"}
                    {b.id === "okx" && "⚫"}
                    {b.name}
                    {b.connected && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)]" />
                    )}
                    {!b.connected && b.implemented && (
                      <span className="text-[8px] opacity-60">no conectado</span>
                    )}
                    {!b.implemented && (
                      <span className="text-[8px] opacity-60">proximamente</span>
                    )}
                  </button>
                );
              })}
            </div>
            {!brokers.some((b) => b.connected) && (
              <p className="text-[10px] text-[var(--color-text-muted)] mt-2">
                💡 No tienes ningún broker conectado. Ve a <strong>Connections</strong> para conectar tu cuenta de Binance u otro exchange.
              </p>
            )}
          </div>
        )}

        {/* Budget allocation panel - only for live mode with a real broker */}
        {tradeMode === "live" && selectedBroker !== "paper" && selectedBroker !== "mock" && (
          <div className="mt-3 rounded-[10px] border border-green-500/30 bg-green-500/5 p-3 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-bold text-green-400">💰 Presupuesto de Trading</span>
              {allocatedCapital > 0 ? (
                <span className="px-2 py-0.5 rounded-[4px] text-[9px] font-bold bg-green-500/20 text-green-400 border border-green-500/40">
                  LÍMITE: ${allocatedCapital.toFixed(2)}
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-[4px] text-[9px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/40">
                  AUTO: Todo el saldo disponible
                </span>
              )}
            </div>

            {/* Balance display */}
            {brokerBalance?.error ? (
              <div className="text-[11px] text-red-400">{brokerBalance.error}</div>
            ) : brokerBalance ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">USDT Libre</div>
                  <div className="text-[14px] font-bold text-green-400">${brokerBalance.usdt_free?.toFixed(2) || "0.00"}</div>
                </div>
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">Total Portfolio</div>
                  <div className="text-[14px] font-bold text-[var(--color-text)]">${brokerBalance.total_usd?.toFixed(2) || "0.00"}</div>
                </div>
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">Activos</div>
                  <div className="text-[14px] font-bold text-[var(--color-text)]">{brokerBalance.assets?.length || 0}</div>
                </div>
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">En MXN</div>
                  <div className="text-[14px] font-bold text-[var(--color-text)]">${brokerBalance.total_mxn?.toFixed(2) || "0.00"}</div>
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-[var(--color-text-muted)]">Cargando saldo...</div>
            )}

            {/* Asset list */}
            {brokerBalance?.assets && brokerBalance.assets.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {brokerBalance.assets.slice(0, 8).map((a: any) => (
                  <div key={a.asset} className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-surface-2)] text-[10px]">
                    <CryptoIcon symbol={a.asset + "USDT"} size={14} />
                    <span className="font-bold text-[var(--color-text)]">{a.asset}</span>
                    <span className="text-[var(--color-text-muted)]">{a.free.toFixed(4)}</span>
                    <span className="text-green-400/70">${a.usd_value.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Capital assignment controls */}
            <div className="flex items-center gap-2 pt-2 border-t border-green-500/20">
              <Input
                type="number"
                value={capitalInput}
                onChange={(e) => setCapitalInput(e.target.value)}
                placeholder="Pon un límite (USD) - ej: 100"
                disabled={isRunning}
                className="flex-1"
              />
              <Tooltip text="Fija un límite maximo de dinero que la IA puede usar. Ej: $100 = la IA nunca usará más de $100.">
                <Button variant="primary" size="sm" onClick={assignCapital} disabled={isRunning || !capitalInput}>
                  Fijar límite
                </Button>
              </Tooltip>
              <Tooltip text="La IA usará todo el USDT disponible en tu cuenta. Sin límite fijo.">
                <Button variant="ghost" size="sm" onClick={useAllBalance} disabled={isRunning}>
                  Sin límite
                </Button>
              </Tooltip>
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)]">
              💡 <strong>Fijar límite</strong> = la IA solo usa ese monto. <strong>Sin límite</strong> = usa todo el USDT disponible.
              El saldo se actualiza cada 30s. Cuando la IA compra, el USDT libre baja en tu broker.
            </div>
          </div>
        )}

        {/* Config panel (collapsible - opciones avanzadas) */}
        {showConfig && (
          <div className="mt-4 pt-4 border-t border-[var(--color-border)] space-y-3">
            <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">- Opciones Avanzadas</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Proveedor de IA</label>
                <Select value={provider} onChange={(e) => { setProvider(e.target.value); const ms = MODELS[e.target.value]; if (ms) setModel(ms[0].value); }} disabled={isRunning} className="w-full">
                  {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Modelo</label>
                <Select value={model} onChange={(e) => setModel(e.target.value)} disabled={isRunning} className="w-full">
                  {(MODELS[provider] || []).map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Intervalo (segundos)</label>
                <div className="flex gap-1">
                  <Input type="number" value={interval} onChange={(e) => setIntervalVal(parseInt(e.target.value) || 30)} min={10} disabled={isRunning} className="w-20" />
                  <Tooltip text="Cada cuántos segundos la IA analiza el mercado. Menos = más frecuente pero gasta más cuota.">
                    <Button variant="primary" size="sm" onClick={setIntervalApi} disabled={isRunning}>Aplicar</Button>
                  </Tooltip>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {provider === "groq" && (
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Groq API Key {isFree && <span className="text-[var(--color-warning)]">*requerido</span>}
                    {hasGroqKey && <span className="text-[var(--color-success)] ml-1">- guardada</span>}
                  </label>
                  <Input type="password" value={groqKey} onChange={(e) => setGroqKey(e.target.value)} placeholder={hasGroqKey ? "Usando key guardada" : isFree ? "Pega tu key gratis de Groq" : "Key del servidor disponible"} disabled={isRunning} className="w-full" />
                  <a href="https://console.groq.com/keys" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key gratis -</a>
                </div>
              )}
              {provider === "gemini" && (
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Gemini API Key {isFree && <span className="text-[var(--color-warning)]">*requerido</span>}
                    {hasGeminiKey && <span className="text-[var(--color-success)] ml-1">- guardada</span>}
                  </label>
                  <Input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder={hasGeminiKey ? "Usando key guardada" : isFree ? "Pega tu key gratis de Gemini" : "Key del servidor disponible"} disabled={isRunning} className="w-full" />
                  <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key gratis -</a>
                </div>
              )}
              {PROVIDERS.find((p) => p.value === provider)?.premium && (
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    API Key Premium {hasPremiumKey && <span className="text-[var(--color-success)] ml-1">- guardada</span>}
                  </label>
                  <Input type="password" value={premiumKey} onChange={(e) => setPremiumKey(e.target.value)} placeholder={hasPremiumKey ? "Usando key guardada" : "Pega tu API key"} disabled={isRunning} className="w-full" />
                  {provider === "openai" && <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key -</a>}
                  {provider === "deepseek" && <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key -</a>}
                  {provider === "mistral" && <a href="https://console.mistral.ai/api-keys" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key -</a>}
                </div>
              )}
            </div>
            <div className="flex gap-3 items-center flex-wrap">
              <Tooltip text="Verifica que tu API key del proveedor de IA funcione correctamente.">
                <Button variant="default" size="sm" onClick={testKey} disabled={isRunning}>Probar API Key</Button>
              </Tooltip>
              {testResult && <span className="text-[12px] font-bold">{testResult}</span>}
            </div>

            {/* Nivel 1: Filtros Inteligentes */}
            <div className="mt-4 pt-4 border-t border-[var(--color-border)] space-y-3">
              <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">🧠 Filtros Inteligentes</div>

              {/* Feature toggles */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <Tooltip text="La IA detecta si el mercado está en tendencia, lateral, o volátil. No compra en tendencia bajista.">
                  <label className="flex items-center gap-2 rounded-[8px] bg-[var(--color-surface-2)] p-2 cursor-pointer">
                    <input type="checkbox" checked={useRegime} onChange={(e) => setUseRegime(e.target.checked)} disabled={isRunning} className="w-4 h-4 accent-[var(--color-accent)]" />
                    <span className="text-[11px] font-bold text-[var(--color-text)]">Market Regime</span>
                    <span className="text-[9px] text-[var(--color-text-muted)]">No compra en bajista</span>
                  </label>
                </Tooltip>
                <Tooltip text="Confirma con timeframe mayor (2h) antes de comprar en 1h. Reduce falsas entradas.">
                  <label className="flex items-center gap-2 rounded-[8px] bg-[var(--color-surface-2)] p-2 cursor-pointer">
                    <input type="checkbox" checked={useMtf} onChange={(e) => setUseMtf(e.target.checked)} disabled={isRunning} className="w-4 h-4 accent-[var(--color-accent)]" />
                    <span className="text-[11px] font-bold text-[var(--color-text)]">MTF Confirm</span>
                    <span className="text-[9px] text-[var(--color-text-muted)]">Confirma 2h trend</span>
                  </label>
                </Tooltip>
                <Tooltip text="Evita comprar símbolos correlacionados con posiciones existentes (ej: no comprar ETH si ya tienes BTC).">
                  <label className="flex items-center gap-2 rounded-[8px] bg-[var(--color-surface-2)] p-2 cursor-pointer">
                    <input type="checkbox" checked={useCorrelation} onChange={(e) => setUseCorrelation(e.target.checked)} disabled={isRunning} className="w-4 h-4 accent-[var(--color-accent)]" />
                    <span className="text-[11px] font-bold text-[var(--color-text)]">Correlation Filter</span>
                    <span className="text-[9px] text-[var(--color-text-muted)]">Diversificación real</span>
                  </label>
                </Tooltip>
              </div>

              {/* Whitelist / Blacklist */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Lista Blanca (solo estos símbolos)
                  </label>
                  <Input
                    value={whitelist}
                    onChange={(e) => setWhitelist(e.target.value)}
                    placeholder="ej: BTCUSDT,ETHUSDT,SOLUSDT (vacío = todos)"
                    disabled={isRunning}
                    className="w-full"
                  />
                  <p className="text-[9px] text-[var(--color-text-muted)] mt-1">Si pones símbolos, la IA SOLO podrá tocar esos.</p>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Lista Negra (nunca tocar)
                  </label>
                  <Input
                    value={blacklist}
                    onChange={(e) => setBlacklist(e.target.value)}
                    placeholder="ej: SHIBUSDT,PEPEUSDT (símbolos a evitar)"
                    disabled={isRunning}
                    className="w-full"
                  />
                  <p className="text-[9px] text-[var(--color-text-muted)] mt-1">La IA nunca comprará estos símbolos.</p>
                </div>
              </div>

              {/* Nivel 3: Custom Instructions */}
              <div className="mt-3">
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                  Instrucciones Personalizadas (lenguaje natural)
                </label>
                <Tooltip text="Escribe reglas en lenguaje natural que la IA debe seguir siempre. Ej: 'No comprar meme coins', 'Solo operar de lunes a viernes', 'Evitar símbolos con volumen bajo'.">
                  <textarea
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    placeholder="ej: No comprar meme coins. Solo operar BTC y ETH los fines de semana. Evitar símbolos con menos de $10M volumen diario."
                    disabled={isRunning}
                    rows={3}
                    className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] resize-none"
                  />
                </Tooltip>
                <p className="text-[9px] text-[var(--color-text-muted)] mt-1">
                  La IA leerá estas reglas en cada ciclo y las respetará. Máx 1000 caracteres.
                </p>
              </div>

              <Button variant="primary" size="sm" onClick={saveSymbolSettings} disabled={isRunning}>
                Guardar Filtros
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Stats Dashboard - en espanol */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Card>
          <CardLabel>Operaciones</CardLabel>
          <CardValue className="text-[var(--color-primary)]">{totalTrades}</CardValue>
        </Card>
        <Card>
          <CardLabel>% Aciertos</CardLabel>
          <CardValue className={winRate >= 50 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {winRate.toFixed(1)}%
          </CardValue>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">{wins} ganadas / {losses} pérdidas</div>
        </Card>
        <Card>
          <CardLabel>Ganancia Total</CardLabel>
          <CardValue className={totalPnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} USDT
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Posiciones Abiertas</CardLabel>
          <CardValue className="text-[var(--color-accent)]">{openPositions}</CardValue>
        </Card>
        <Card>
          <CardLabel>Ciclos</CardLabel>
          <CardValue>{cycles}</CardValue>
        </Card>
        <Card>
          <CardLabel>Decisiones</CardLabel>
          <CardValue>
            <span className="text-[var(--color-success)]">{decisionsWithActions}</span>
            <span className="text-[var(--color-text-muted)] mx-1">/</span>
            <span className="text-[var(--color-text-muted)]">{decisionsHold}</span>
            <span className="text-[10px] text-[var(--color-text-muted)] ml-1">act/hold</span>
          </CardValue>
        </Card>
      </div>

      {/* PnL Chart */}
      {cumulativePnl.length > 1 && (
        <Card>
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Ganancia Acumulada (operaciones cerradas)</h3>
          <PnlSparkline data={cumulativePnl} />
        </Card>
      )}

      {/* By symbol breakdown */}
      {stats?.by_symbol && Object.keys(stats.by_symbol).length > 0 && (
        <Card>
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Resultado por Moneda</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(stats.by_symbol).map(([sym, data]: [string, any]) => (
              <div key={sym} className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5">
                <div className="flex items-center justify-between mb-1">
                  <span className="flex items-center gap-1.5 text-[12px] font-bold text-[var(--color-text)]">
                    <CryptoIcon symbol={sym} size={16} />
                    {sym}
                  </span>
                  <span className={cn(
                    "text-[11px] font-bold",
                    data.pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                  )}>
                    {data.pnl >= 0 ? "+" : ""}{data.pnl.toFixed(2)}
                  </span>
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)]">
                  {data.buys} compras / {data.sells} ventas ? {data.wins}G/{data.losses}P
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Nivel 2: Performance Learning — que factores funcionan mejor */}
      {perfData && perfData.status === "ok" && Object.keys(perfData.factors || {}).length > 0 && (
        <Card>
          <h3 className="text-[13px] font-bold text-[var(--color-accent)] mb-3">🎓 Aprendizaje de la IA — Que estrategias funcionan mejor</h3>
          <p className="text-[11px] text-[var(--color-text-muted)] mb-3">
            La IA trackea que factores (RSI, regimen, tendencia) correlatean con operaciones ganadoras.
            Basado en {perfData.total_records} operaciones evaluadas.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries(perfData.factors).slice(0, 9).map(([factor, data]: [string, any]) => (
              <div key={factor} className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-bold text-[var(--color-text)]">{factor}</span>
                  <span className={cn(
                    "text-[11px] font-bold",
                    data.win_rate >= 0.6 ? "text-[var(--color-success)]" : data.win_rate >= 0.4 ? "text-[var(--color-warning)]" : "text-[var(--color-danger)]"
                  )}>
                    {(data.win_rate * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="text-[9px] text-[var(--color-text-muted)]">{data.total} operaciones</div>
                <div className="mt-1 h-1 rounded-full bg-[var(--color-border)] overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      data.win_rate >= 0.6 ? "bg-[var(--color-success)]" : data.win_rate >= 0.4 ? "bg-[var(--color-warning)]" : "bg-[var(--color-danger)]"
                    )}
                    style={{ width: `${data.win_rate * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Nivel 3: AI vs Backtest Comparison */}
      {backtestData && backtestData.status === "ok" && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[13px] font-bold text-[var(--color-accent)]">📊 IA vs Buy & Hold BTC — Últimos {backtestData.days} días</h3>
            <div className="flex gap-1">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setBacktestDays(d)}
                  className={cn(
                    "px-2 py-0.5 rounded-[6px] text-[10px] font-bold transition-colors",
                    backtestDays === d
                      ? "bg-[var(--color-accent)] text-[var(--color-bg)]"
                      : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  )}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-3">
            {/* AI Agent */}
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3">
              <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">🤖 AI Agent</div>
              <div className={cn(
                "text-[20px] font-bold",
                backtestData.ai_agent.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                {backtestData.ai_agent.pnl_pct >= 0 ? "+" : ""}{backtestData.ai_agent.pnl_pct}%
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
                ${backtestData.ai_agent.total_pnl} PnL · {backtestData.ai_agent.total_trades} trades
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)]">
                Win rate: {backtestData.ai_agent.win_rate}% · Avg: ${backtestData.ai_agent.avg_trade}
              </div>
            </div>

            {/* Buy & Hold BTC */}
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3">
              <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">📈 Buy & Hold BTC</div>
              <div className={cn(
                "text-[20px] font-bold",
                backtestData.buy_hold_btc.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                {backtestData.buy_hold_btc.pnl_pct >= 0 ? "+" : ""}{backtestData.buy_hold_btc.pnl_pct}%
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
                ${backtestData.buy_hold_btc.pnl_usd} PnL · mismo capital
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)]">
                BTC: ${backtestData.buy_hold_btc.btc_price_then} → ${backtestData.buy_hold_btc.btc_price_now}
              </div>
            </div>
          </div>

          {/* Verdict */}
          <div className={cn(
            "rounded-[8px] p-2.5 text-center",
            backtestData.comparison.winner === "ai_agent"
              ? "bg-[var(--color-success)]/10 border border-[var(--color-success)]/30"
              : "bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30"
          )}>
            <span className="text-[12px] font-bold">
              {backtestData.comparison.winner === "ai_agent"
                ? `🤖 La IA ganó por ${backtestData.comparison.ai_vs_btc_pct > 0 ? "+" : ""}${backtestData.comparison.ai_vs_btc_pct}% (${backtestData.comparison.ai_vs_btc_usd > 0 ? "+" : ""}$${backtestData.comparison.ai_vs_btc_usd})`
                : `📈 Buy & Hold BTC ganó por ${backtestData.comparison.ai_vs_btc_pct < 0 ? "+" : ""}${Math.abs(backtestData.comparison.ai_vs_btc_pct)}% ($${Math.abs(backtestData.comparison.ai_vs_btc_usd).toFixed(2)})`
              }
            </span>
          </div>

          {/* Best/Worst */}
          {backtestData.ai_agent.total_trades > 0 && (
            <div className="flex gap-3 mt-2 text-[10px]">
              <span className="text-[var(--color-success)]">Mejor: +{backtestData.ai_agent.best_trade_pct}%</span>
              <span className="text-[var(--color-danger)]">Peor: {backtestData.ai_agent.worst_trade_pct}%</span>
            </div>
          )}
        </Card>
      )}

      {/* Reasoning Cards */}
      {decisions.length > 0 && (
        <Card>
          <h3 className="text-[13px] font-bold text-[var(--color-accent)] mb-3">🧠 Razonamiento de la IA - Últimas Decisiones</h3>
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {decisions.slice(0, 10).map((d, i) => (
              <ReasoningCard key={i} entry={d} defaultExpanded={i < 3} />
            ))}
          </div>
        </Card>
      )}

      {/* Activity Feed */}
      <Card>
        <h3 className="text-[13px] font-bold text-[var(--color-accent)] mb-3">
          {isRunning && <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] mr-2 animate-pulse" />}
          Actividad en Tiempo Real
        </h3>
        <div className="bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)] p-3 max-h-80 overflow-y-auto font-mono text-[11px] space-y-0.5">
          {activityLog.length === 0 ? (
            <p className="text-[var(--color-text-muted)] text-center py-8 text-[12px]">
              Activa el asistente para ver su actividad en tiempo real.
            </p>
          ) : (
            activityLog.map((entry, i) => {
              const time = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString("en-US", { hour12: false }) : "";
              const level = entry.level || "info";
              const color = level === "error" ? "text-[var(--color-danger)]"
                : level === "warn" ? "text-[var(--color-warning)]"
                : entry.phase === "decision" ? "text-[var(--color-accent)]"
                : "text-[var(--color-text)]";
              return (
                <div key={i} className="flex gap-2">
                  <span className="text-[var(--color-text-muted)] flex-shrink-0">{time}</span>
                  <span className={color}>{entry.message}</span>
                </div>
              );
            })
          )}
        </div>
      </Card>
    </div>
  );
}

function PnlSparkline({ data }: { data: number[] }) {
  if (data.length < 2) return <p className="text-[12px] text-[var(--color-text-muted)]">Not enough data yet</p>;
  const w = 800;
  const h = 120;
  const min = Math.min(...data, 0);
  const max = Math.max(...data, 0);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");
  const zeroY = h - ((0 - min) / range) * h;
  const isPositive = data[data.length - 1] >= 0;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 120 }}>
      <line x1={0} y1={zeroY} x2={w} y2={zeroY} stroke="var(--color-border)" strokeDasharray="3,3" />
      <polyline
        points={points}
        fill="none"
        stroke={isPositive ? "var(--color-success)" : "var(--color-danger)"}
        strokeWidth={2}
      />
      <text x={4} y={14} fill="var(--color-text-muted)" fontSize={10}>{max.toFixed(2)}</text>
      <text x={4} y={h - 4} fill="var(--color-text-muted)" fontSize={10}>{min.toFixed(2)}</text>
    </svg>
  );
}

function ReasoningCard({ entry, defaultExpanded = false }: { entry: any; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const actions: any[] = entry.actions || [];
  const time = entry.timestamp ? new Date(entry.timestamp).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  const hasActions = actions.length > 0;

  return (
    <div
      className={cn(
        "rounded-[10px] border p-3 cursor-pointer transition-all",
        hasActions
          ? "bg-[var(--color-accent)]/5 border-[var(--color-accent)]/30 hover:bg-[var(--color-accent)]/10"
          : "bg-[var(--color-surface-2)] border-[var(--color-border)]"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={cn(
            "text-[10px] font-bold px-2 h-5 rounded flex items-center",
            hasActions ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          )}>
            Cycle {entry.cycle}
          </span>
          <span className="text-[11px] text-[var(--color-text-muted)]">{time}</span>
        </div>
        <div className="flex items-center gap-2">
          {hasActions ? (
            actions.map((a, i) => (
              <span key={i} className={cn(
                "text-[10px] font-bold px-2 h-5 rounded flex items-center gap-1",
                a.type === "buy" ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
              )}>
                <CryptoIcon symbol={a.symbol} size={12} />
                {a.type === "buy" ? "BUY" : "SELL"} {a.symbol}
                {a.confidence && <span className="ml-1 opacity-60">{Math.round(a.confidence * 100)}%</span>}
              </span>
            ))
          ) : (
            <span className="text-[10px] font-bold text-[var(--color-text-muted)]">HOLD</span>
          )}
          <span className="text-[10px] text-[var(--color-text-muted)]">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && (
        <div className="mt-3 space-y-2">
          {entry.market_overview && (
            <div>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Market Overview</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.market_overview}</p>
            </div>
          )}
          {entry.analysis && (
            <div>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Analysis</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.analysis}</p>
            </div>
          )}
          {entry.risk_assessment && (
            <div>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Risk Assessment</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.risk_assessment}</p>
            </div>
          )}
          {actions.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Actions</span>
              {actions.map((a, i) => (
                <div key={i} className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      "text-[11px] font-bold flex items-center gap-1",
                      a.type === "buy" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                    )}>
                      <CryptoIcon symbol={a.symbol} size={14} />
                      {a.type === "buy" ? "BUY" : "SELL"} {a.symbol}
                    </span>
                    {a.confidence != null && (
                      <span className="text-[10px] font-bold text-[var(--color-accent)]">
                        {Math.round(a.confidence * 100)}% confidence
                      </span>
                    )}
                    {a.stop_loss_pct && (
                      <span className="text-[10px] text-[var(--color-danger)]">SL: {a.stop_loss_pct}%</span>
                    )}
                    {a.take_profit_pct && (
                      <span className="text-[10px] text-[var(--color-success)]">TP: {a.take_profit_pct}%</span>
                    )}
                  </div>
                  {a.reason && <p className="text-[11px] text-[var(--color-text-muted)]">{a.reason}</p>}
                </div>
              ))}
            </div>
          )}
          {entry.next_steps && (
            <div>
              <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Next Steps</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.next_steps}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
