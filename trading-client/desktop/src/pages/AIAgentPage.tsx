import { useEffect, useState, useCallback } from "react";
import { Bot, Power, BarChart3, Lightbulb, GraduationCap, Zap, Activity, BrainCircuit } from "lucide-react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Tabs } from "../components/ui/Tabs";
import { toast } from "../components/ui/Toast";
import { cn, fmtTime, fmtDateTime } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { Tooltip } from "../components/common/Tooltip";

const PROVIDERS = [
  { value: "omniroute", label: "OmniRoute (Gateway 291 providers) - Gratis" },
  { value: "gemini", label: "Gemini (Google Cloud) - Gratis" },
  { value: "groq", label: "Groq (Cloud) - Gratis" },
  { value: "ollama", label: "Ollama (Local) - Gratis" },
  { value: "openai", label: "OpenAI (GPT-4o) - Premium", premium: true },
  { value: "deepseek", label: "DeepSeek - Premium", premium: true },
  { value: "mistral", label: "Mistral AI - Premium", premium: true },
];

const MODELS: Record<string, { value: string; label: string }[]> = {
  omniroute: [
    { value: "auto", label: "Auto (Smart Routing - recomendado)" },
    { value: "auto/coding", label: "Auto/Coding (calidad primero)" },
    { value: "auto/fast", label: "Auto/Fast (menor latencia)" },
    { value: "auto/cheap", label: "Auto/Cheap (mas barato)" },
    { value: "auto/offline", label: "Auto/Offline (mas quota)" },
    { value: "auto/smart", label: "Auto/Smart (calidad + exploracion)" },
    { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5 (via OmniRoute)" },
    { value: "gpt-4o", label: "GPT-4o (via OmniRoute)" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash (via OmniRoute)" },
    { value: "deepseek-v3", label: "DeepSeek V3 (via OmniRoute)" },
    { value: "kimi-k3", label: "Kimi K3 (via OmniRoute)" },
    { value: "llama-3.3-70b", label: "Llama 3.3 70B (via OmniRoute)" },
  ],
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

// ─── Multi-Symbol Selector (CCXT dropdown with chips) ───

// Convert CCXT "BTC/USDT" → Binance "BTCUSDT"
function toBinanceSymbol(ccxtSymbol: string): string {
  return ccxtSymbol.replace("/", "").toUpperCase();
}

function MultiSymbolSelector({
  label, description, value, onChange, symbols, loading, disabled,
  quoteAsset, onQuoteChange, quoteAssets, pickerOpen, setPickerOpen,
  search, setSearch,
}: {
  label: string;
  description: string;
  value: string; // comma-separated Binance format
  onChange: (v: string) => void;
  symbols: any[];
  loading: boolean;
  disabled: boolean;
  quoteAsset: string;
  onQuoteChange: (q: string) => void;
  quoteAssets: string[];
  pickerOpen: boolean;
  setPickerOpen: (open: boolean) => void;
  search: string;
  setSearch: (s: string) => void;
}) {
  // Parse current value into array of Binance-format symbols
  const selected: string[] = value ? value.split(",").map(s => s.trim()).filter(Boolean) : [];

  const toggleSymbol = (ccxtSym: string) => {
    const binanceSym = toBinanceSymbol(ccxtSym);
    if (selected.includes(binanceSym)) {
      onChange(selected.filter(s => s !== binanceSym).join(","));
    } else {
      onChange([...selected, binanceSym].join(","));
    }
  };

  const removeSymbol = (binanceSym: string) => {
    onChange(selected.filter(s => s !== binanceSym).join(","));
  };

  const filtered = symbols.filter(s =>
    s.symbol.toLowerCase().includes(search.toLowerCase()) ||
    s.base.toLowerCase().includes(search.toLowerCase())
  ).slice(0, 50);

  return (
    <div>
      <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
        {label}
      </label>

      {/* Selected symbols as chips */}
      <div className="flex flex-wrap gap-1 mb-1.5 min-h-[28px] rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-1.5">
        {selected.length === 0 && (
          <span className="text-[11px] text-[var(--color-text-muted)] py-0.5 px-1">
            {description}
          </span>
        )}
        {selected.map(sym => (
          <span
            key={sym}
            className="inline-flex items-center gap-1 rounded-[4px] bg-[var(--color-primary)]/15 px-1.5 py-0.5 text-[11px] font-bold text-[var(--color-text)]"
          >
            {sym}
            {!disabled && (
              <button
                onClick={() => removeSymbol(sym)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)] text-[11px] leading-none"
              >
                ×
              </button>
            )}
          </span>
        ))}
      </div>

      {/* Add symbol button + dropdown */}
      <div className="relative">
        <button
          onClick={() => !disabled && setPickerOpen(!pickerOpen)}
          disabled={disabled}
          className={cn(
            "w-full flex items-center justify-between rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2.5 py-1.5 text-[11px]",
            disabled ? "opacity-50 cursor-not-allowed" : "hover:border-[var(--color-primary)]"
          )}
        >
          <span className="text-[var(--color-text-muted)]">
            {loading ? "Cargando símbolos..." : "+ Añadir símbolo"}
          </span>
          <span className="text-[var(--color-text-muted)]">▼</span>
        </button>

        {pickerOpen && !disabled && (
          <div className="absolute z-50 mt-1 w-full rounded-[8px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-xl max-h-[300px] flex flex-col">
            {/* Quote asset selector */}
            <div className="flex gap-1 p-1.5 border-b border-[var(--color-border)] flex-wrap">
              {(quoteAssets.length > 0 ? quoteAssets.slice(0, 8) : ["USDT", "BTC", "ETH", "FDUSD", "BNB"]).map(q => (
                <button
                  key={q}
                  onClick={() => onQuoteChange(q)}
                  className={cn(
                    "px-1.5 py-0.5 rounded-[4px] text-[11px] font-bold transition-colors",
                    quoteAsset === q
                      ? "bg-[var(--color-primary)] text-white"
                      : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  )}
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Search */}
            <input
              autoFocus
              placeholder="Buscar (BTC, ETH, SOL...)"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full bg-[var(--color-surface-2)] border-b border-[var(--color-border)] p-2 text-[11px] outline-none"
            />

            {/* Results */}
            <div className="overflow-y-auto flex-1">
              {loading && (
                <div className="p-3 text-center text-[11px] text-[var(--color-text-muted)]">Cargando...</div>
              )}
              {!loading && filtered.length === 0 && (
                <div className="p-3 text-center text-[11px] text-[var(--color-text-muted)]">Sin resultados</div>
              )}
              {!loading && filtered.map(s => {
                const binanceSym = toBinanceSymbol(s.symbol);
                const isSelected = selected.includes(binanceSym);
                return (
                  <button
                    key={s.symbol}
                    onClick={() => toggleSymbol(s.symbol)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-1.5 text-[11px] hover:bg-[var(--color-surface-2)] transition-colors text-left",
                      isSelected && "bg-[var(--color-primary)]/10"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className={cn("w-3 text-center", isSelected ? "text-[var(--color-success)]" : "text-transparent")}>✓</span>
                      <span className="font-bold text-[var(--color-text)]">{s.base}</span>
                      <span className="text-[var(--color-text-muted)] text-[11px]">/{s.quote}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-[var(--color-text-muted)]">
                      {s.last_price > 0 && (
                        <span>${s.last_price < 1 ? s.last_price.toFixed(6) : s.last_price.toLocaleString()}</span>
                      )}
                      {s.change_pct !== 0 && (
                        <span className={s.change_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
                          {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{description}</p>
    </div>
  );
}

export function AIAgentPage() {
  const [status, setStatus] = useState<any>(null);
  const [log, setLog] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-flash-latest");
  const [interval, setIntervalVal] = useState(30);
  const [tradeMode, setTradeMode] = useState<"paper" | "live">("live");
  const [autoTrade, setAutoTrade] = useState(true);
  const [groqKey, setGroqKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [premiumKey, setPremiumKey] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [aiMode, setAiMode] = useState<"conservative" | "balanced" | "aggressive">("balanced");
  const [showConfig, setShowConfig] = useState(false);
  const [plan, setPlan] = useState<any>(null);
  const [brokers, setBrokers] = useState<any[]>([]);
  const [selectedBroker, setSelectedBroker] = useState<string>("binance");
  const [brokerBalance, setBrokerBalance] = useState<any>(null);
  const [allocatedCapital, setAllocatedCapital] = useState<number>(0);
  const [capitalInput, setCapitalInput] = useState<string>("");
  // Nivel 1: Symbol controls + feature toggles
  const [whitelist, setWhitelist] = useState("");
  const [blacklist, setBlacklist] = useState("");
  // Symbol dropdown state (from CCXT)
  const [aiSymbols, setAiSymbols] = useState<any[]>([]);
  const [aiSymbolsLoading, setAiSymbolsLoading] = useState(false);
  const [aiQuoteAsset, setAiQuoteAsset] = useState("USDT");
  const [aiQuoteAssets, setAiQuoteAssets] = useState<string[]>([]);
  const [whitelistPickerOpen, setWhitelistPickerOpen] = useState(false);
  const [blacklistPickerOpen, setBlacklistPickerOpen] = useState(false);
  const [whitelistSearch, setWhitelistSearch] = useState("");
  const [blacklistSearch, setBlacklistSearch] = useState("");
  const [useRegime, setUseRegime] = useState(true);
  const [useMtf, setUseMtf] = useState(true);
  const [useCorrelation, setUseCorrelation] = useState(true);
  // Nivel 2: Performance learning
  const [perfData, setPerfData] = useState<any>(null);
  const [learningInsights, setLearningInsights] = useState<any>(null);
  // Nivel 3: Custom instructions + backtest comparison
  const [customInstructions, setCustomInstructions] = useState("");
  const [backtestData, setBacktestData] = useState<any>(null);
  const [backtestDays, setBacktestDays] = useState(30);
  // Fase 1: Short trading + leverage
  const [shortsEnabled, setShortsEnabled] = useState(false);
  const [leverage, setLeverage] = useState(1);
  // UX: Tab state
  const [activeTab, setActiveTab] = useState("config");

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
      setSelectedBroker(r.current || "binance");
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

  const loadAiSymbols = useCallback(async (quote: string = "USDT") => {
    setAiSymbolsLoading(true);
    try {
      const r = await api<any>(`/api/bots/symbols?quote=${quote}&limit=300`);
      if (r.status === "ok") {
        setAiSymbols(r.symbols || []);
        setAiQuoteAssets(r.quote_assets || []);
      }
    } catch {} finally {
      setAiSymbolsLoading(false);
    }
  }, []);

  const loadPerfData = useCallback(async () => {
    try {
      const r = await api<any>("/api/ai-agent/performance-learning");
      setPerfData(r);
    } catch {}
  }, []);

  const loadLearningInsights = useCallback(async () => {
    try {
      const r = await api<any>("/api/ai-agent/learning-insights");
      setLearningInsights(r);
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
    loadAiSymbols("USDT");
    loadPerfData();
    loadLearningInsights();
    loadBacktest();
    const id1 = setInterval(loadStatus, 5000);
    const id2 = setInterval(loadLog, 5000);
    const id3 = setInterval(loadStats, 15000);
    const id4 = setInterval(loadPerfData, 60000);
    const id5 = setInterval(loadLearningInsights, 60000);
    return () => {
      clearInterval(id1);
      clearInterval(id2);
      clearInterval(id3);
      clearInterval(id4);
      clearInterval(id5);
    };
  }, [loadStatus, loadLog, loadStats, loadPlan, loadBrokers, loadTradingMode, loadSymbolSettings, loadPerfData, loadLearningInsights, loadBacktest]);

  // Reload symbols when quote asset changes
  useEffect(() => {
    loadAiSymbols(aiQuoteAsset);
  }, [aiQuoteAsset, loadAiSymbols]);

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
  const byokReady = (provider === "groq" && (hasGroqKey || !!groqKey)) || (provider === "gemini" && (hasGeminiKey || !!geminiKey)) || provider === "omniroute" || provider === "ollama";
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
      {/* Hero compacto — status + controles */}
      <div className="panel-hero p-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-12 h-12 rounded-xl flex items-center justify-center",
              isRunning ? "bg-[var(--color-success)]/15" : "bg-[var(--color-surface-2)]"
            )}>
              {isRunning ? (
                <Bot size={22} className="text-[var(--color-success)]" />
              ) : (
                <Power size={22} className="text-[var(--color-text-muted)]" />
              )}
            </div>
            <div>
              <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">Asistente de Trading con IA</h2>
              <p className="text-[12px] text-[var(--color-text-muted)]">
                {isRunning ? (
                  <>
                    <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] mr-1.5 animate-pulse" />
                    Analizando mercado · Ciclo {cycles} · {status?.model || "IA"}
                  </>
                ) : (
                  "Detenido — clic en Activar para empezar"
                )}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Tooltip text="Inicia el asistente. Analiza el mercado y genera señales de compra/venta automáticamente.">
              <Button variant="success" onClick={start} disabled={!canStart || isRunning} className="h-9 btn-press">▶ Activar</Button>
            </Tooltip>
            <Tooltip text="Detiene el asistente. Las posiciones abiertas se mantienen hasta SL/TP.">
              <Button variant="danger" onClick={stop} disabled={!isRunning} className="h-9 btn-press">⏹ Detener</Button>
            </Tooltip>
            <Tooltip text="Muestra u oculta opciones avanzadas: proveedor de IA, API key, intervalo.">
              <Button variant="default" onClick={() => setShowConfig(!showConfig)} disabled={isRunning} className="h-9 btn-press">⚙ Avanzado</Button>
            </Tooltip>
          </div>
        </div>

        {/* Plan badge + quota info + BYOK — compact, inline */}
        <div className="flex items-center gap-3 flex-wrap mt-3">
          <span className={cn(
            "text-[11px] font-bold px-2.5 h-6 rounded-full flex items-center uppercase tracking-wide",
            isPaid
              ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          )}>
            {isPaid ? "⭐ " : ""}{subscription}
          </span>
          <span className="text-[11px] text-[var(--color-text-muted)]">
            {maxRequestsPerDay === 99999 ? "Ilimitado" : `${maxRequestsPerDay} análisis/día`} · min intervalo {minInterval}s
          </span>
        </div>

        {needsByok && !byokReady && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30">
            <p className="text-[12px] font-bold text-[var(--color-warning)]">
              Necesitas una API key gratuita para usar este proveedor de IA
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              {provider === "groq" ? (
                <>Obtén una key gratis en <a href="https://console.groq.com/keys" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline">console.groq.com/keys</a> y pégala en el tab Config abajo.</>
              ) : (
                <>Obtén una key gratis en <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline">aistudio.google.com/apikey</a> y pégala en el tab Config abajo.</>
              )}
            </p>
          </div>
        )}

        {isPremiumProvider && isFree && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
            <p className="text-[12px] font-bold text-[var(--color-danger)]">
              {provider} requiere suscripción PRO o PREMIUM
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              Mejora tu plan para usar proveedores de IA premium, o usa Groq/Gemini (gratis) con tu propia key.
            </p>
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "config", label: "Configuración", icon: <Zap size={15} /> },
          { id: "performance", label: "Performance", icon: <BarChart3 size={15} /> },
          { id: "activity", label: "Actividad", icon: <Activity size={15} /> },
          { id: "reasoning", label: "Razonamiento", icon: <BrainCircuit size={15} />, badge: decisions.length > 0 ? <span className="text-[11px] font-bold text-[var(--color-text-muted)]">{decisions.length}</span> : undefined },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      <div className="animate-fade-in-up" key={activeTab}>
        {activeTab === "config" && (
          <AgentConfigTab
            isRunning={isRunning}
            tradeMode={tradeMode}
            setTradeMode={setTradeMode}
            autoTrade={autoTrade}
            toggleAutoTrade={toggleAutoTrade}
            aiMode={aiMode}
            setAiMode={setAiMode}
            showConfig={showConfig}
            setShowConfig={setShowConfig}
            brokers={brokers}
            selectedBroker={selectedBroker}
            selectBroker={selectBroker}
            brokerBalance={brokerBalance}
            allocatedCapital={allocatedCapital}
            capitalInput={capitalInput}
            setCapitalInput={setCapitalInput}
            assignCapital={assignCapital}
            useAllBalance={useAllBalance}
            provider={provider}
            setProvider={setProvider}
            model={model}
            setModel={setModel}
            interval={interval}
            setIntervalVal={setIntervalVal}
            setIntervalApi={setIntervalApi}
            groqKey={groqKey}
            setGroqKey={setGroqKey}
            geminiKey={geminiKey}
            setGeminiKey={setGeminiKey}
            premiumKey={premiumKey}
            setPremiumKey={setPremiumKey}
            testKey={testKey}
            testResult={testResult}
            isFree={isFree}
            isPaid={isPaid}
            isPremiumProvider={isPremiumProvider}
            needsByok={needsByok}
            byokReady={byokReady}
            hasGroqKey={hasGroqKey}
            hasGeminiKey={hasGeminiKey}
            hasPremiumKey={hasPremiumKey}
            whitelist={whitelist}
            setWhitelist={setWhitelist}
            blacklist={blacklist}
            setBlacklist={setBlacklist}
            aiSymbols={aiSymbols}
            aiSymbolsLoading={aiSymbolsLoading}
            aiQuoteAsset={aiQuoteAsset}
            setAiQuoteAsset={setAiQuoteAsset}
            aiQuoteAssets={aiQuoteAssets}
            whitelistPickerOpen={whitelistPickerOpen}
            setWhitelistPickerOpen={setWhitelistPickerOpen}
            blacklistPickerOpen={blacklistPickerOpen}
            setBlacklistPickerOpen={setBlacklistPickerOpen}
            whitelistSearch={whitelistSearch}
            setWhitelistSearch={setWhitelistSearch}
            blacklistSearch={blacklistSearch}
            setBlacklistSearch={setBlacklistSearch}
            useRegime={useRegime}
            setUseRegime={setUseRegime}
            useMtf={useMtf}
            setUseMtf={setUseMtf}
            useCorrelation={useCorrelation}
            setUseCorrelation={setUseCorrelation}
            customInstructions={customInstructions}
            setCustomInstructions={setCustomInstructions}
            shortsEnabled={shortsEnabled}
            setShortsEnabled={setShortsEnabled}
            leverage={leverage}
            setLeverage={setLeverage}
            saveSymbolSettings={saveSymbolSettings}
          />
        )}
        {activeTab === "performance" && (
          <AgentPerformanceTab
            stats={stats}
            cycles={cycles}
            cumulativePnl={cumulativePnl}
            totalTrades={totalTrades}
            winRate={winRate}
            totalPnl={totalPnl}
            openPositions={openPositions}
            wins={wins}
            losses={losses}
            decisionsWithActions={decisionsWithActions}
            decisionsHold={decisionsHold}
            perfData={perfData}
            learningInsights={learningInsights}
            backtestData={backtestData}
            backtestDays={backtestDays}
            setBacktestDays={setBacktestDays}
          />
        )}
        {activeTab === "activity" && (
          <AgentActivityTab
            isRunning={isRunning}
            activityLog={activityLog}
          />
        )}
        {activeTab === "reasoning" && (
          <AgentReasoningTab
            decisions={decisions}
          />
        )}
      </div>
    </div>
  );
}

// ─── Config Tab ───
function AgentConfigTab(props: any) {
  const {
    isRunning, tradeMode, setTradeMode, autoTrade, toggleAutoTrade,
    aiMode, setAiMode, showConfig,
    brokers, selectedBroker, selectBroker, brokerBalance,
    allocatedCapital, capitalInput, setCapitalInput, assignCapital, useAllBalance,
    provider, setProvider, model, setModel, interval, setIntervalVal, setIntervalApi,
    groqKey, setGroqKey, geminiKey, setGeminiKey, premiumKey, setPremiumKey,
    testKey, testResult, isFree,
    whitelist, setWhitelist, blacklist, setBlacklist,
    aiSymbols, aiSymbolsLoading, aiQuoteAsset, setAiQuoteAsset, aiQuoteAssets,
    whitelistPickerOpen, setWhitelistPickerOpen, blacklistPickerOpen, setBlacklistPickerOpen,
    whitelistSearch, setWhitelistSearch, blacklistSearch, setBlacklistSearch,
    useRegime, setUseRegime, useMtf, setUseMtf, useCorrelation, setUseCorrelation,
    customInstructions, setCustomInstructions,
    shortsEnabled, setShortsEnabled, leverage, setLeverage, saveSymbolSettings,
  } = props;
  const hasGroqKey = props.hasGroqKey;
  const hasGeminiKey = props.hasGeminiKey;
  const hasPremiumKey = props.hasPremiumKey;

  return (
    <Card>
    {/* --- Paso 1: Modo de operación --- */}
    <div className="mt-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[11px] font-bold flex items-center justify-center">1</span>
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
              <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed">
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
              <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed">
                La IA ejecuta operaciones reales en tu cuenta del broker. <strong>Puedes ganar o perder dinero real.</strong> Solo para usuarios con experiencia.
              </p>
            </button>
          </div>
          {tradeMode === "live" && (
            <div className="mt-2 p-2.5 rounded-[8px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
              <p className="text-[11px] font-bold text-[var(--color-danger)]">
                ⚠️ Modo Dinero Real activado. La IA usará tu saldo del broker para comprar y vender.
              </p>
              <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
                Puedes limitar cuanto dinero usa en la seccion "Presupuesto" abajo. La IA nunca usará más de lo que tu permitas.
              </p>
            </div>
          )}
        </div>

        {/* --- Paso 2: Estilo de trading --- */}
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[11px] font-bold flex items-center justify-center">2</span>
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
                <div className="text-[11px] mt-1 leading-tight opacity-80">{m.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* --- Paso 3: Ejecucion automática --- */}
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[11px] font-bold flex items-center justify-center">3</span>
            <span className="text-[12px] font-bold text-[var(--color-text)]">¿Quieres que la IA ejecute operaciones sola?</span>
          </div>
          <div className="rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-3">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-[12px] font-bold text-[var(--color-text)]">
                  Ejecucion automática {autoTrade ? "(Activada)" : "(Desactivada)"}
                </p>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1 leading-relaxed">
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
                <p className="text-[11px] text-[var(--color-warning)] font-bold">
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
              <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[11px] font-bold flex items-center justify-center">4</span>
              <span className="text-[12px] font-bold text-[var(--color-text)]">¿En qué exchange tienes tu cuenta?</span>
            </div>
            <div className="flex gap-2 flex-wrap">
              {brokers.filter((b: any) => b.id !== "paper").map((b: any) => {
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
                      <span className="text-[11px] opacity-60">no conectado</span>
                    )}
                    {!b.implemented && (
                      <span className="text-[11px] opacity-60">proximamente</span>
                    )}
                  </button>
                );
              })}
            </div>
            {!brokers.some((b: any) => b.connected) && (
              <p className="text-[11px] text-[var(--color-text-muted)] mt-2">
                💡 No tienes ningún broker conectado. Ve a <strong>Connections</strong> para conectar tu cuenta de Binance u otro exchange.
              </p>
            )}
          </div>
        )}

        {/* Budget allocation panel - only for live mode with a real broker */}
        {tradeMode === "live" && selectedBroker !== "paper" && selectedBroker !== "mock" && (
          <div className="mt-3 rounded-[10px] border border-[var(--color-success)]/30 bg-[var(--color-success)]/5 p-3 space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-[12px] font-bold text-[var(--color-success)]">💰 Presupuesto de Trading</span>
              {allocatedCapital > 0 ? (
                <span className="px-2 py-0.5 rounded-[4px] text-[11px] font-bold bg-[var(--color-success)]/20 text-[var(--color-success)] border border-[var(--color-success)]/40">
                  LÍMITE: ${allocatedCapital.toFixed(2)}
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-[4px] text-[11px] font-bold bg-[var(--color-primary)]/20 text-[var(--color-primary)] border border-[var(--color-primary)]/40">
                  AUTO: Todo el saldo disponible
                </span>
              )}
            </div>

            {/* Balance display */}
            {brokerBalance?.error ? (
              <div className="text-[11px] text-[var(--color-danger)]">{brokerBalance.error}</div>
            ) : brokerBalance ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">USDT Libre</div>
                  <div className="text-[14px] font-bold text-[var(--color-success)]">${brokerBalance.usdt_free?.toFixed(2) || "0.00"}</div>
                </div>
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Total Portfolio</div>
                  <div className="text-[14px] font-bold text-[var(--color-text)]">${brokerBalance.total_usd?.toFixed(2) || "0.00"}</div>
                </div>
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Activos</div>
                  <div className="text-[14px] font-bold text-[var(--color-text)]">{brokerBalance.assets?.length || 0}</div>
                </div>
                <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2">
                  <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">En MXN</div>
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
                  <div key={a.asset} className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-surface-2)] text-[11px]">
                    <CryptoIcon symbol={a.asset + "USDT"} size={14} />
                    <span className="font-bold text-[var(--color-text)]">{a.asset}</span>
                    <span className="text-[var(--color-text-muted)]">{a.free.toFixed(4)}</span>
                    <span className="text-[var(--color-success)]/70">${a.usd_value.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Capital assignment controls */}
            <div className="flex items-center gap-2 pt-2 border-t border-[var(--color-success)]/20">
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
            <div className="text-[11px] text-[var(--color-text-muted)]">
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
                <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Proveedor de IA</label>
                <Select value={provider} onChange={(e) => { setProvider(e.target.value); const ms = MODELS[e.target.value]; if (ms) setModel(ms[0].value); }} disabled={isRunning} className="w-full">
                  {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Modelo</label>
                <Select value={model} onChange={(e) => setModel(e.target.value)} disabled={isRunning} className="w-full">
                  {(MODELS[provider] || []).map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Intervalo (segundos)</label>
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
                  <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Groq API Key {isFree && <span className="text-[var(--color-warning)]">*requerido</span>}
                    {hasGroqKey && <span className="text-[var(--color-success)] ml-1">- guardada</span>}
                  </label>
                  <Input type="password" value={groqKey} onChange={(e) => setGroqKey(e.target.value)} placeholder={hasGroqKey ? "Usando key guardada" : isFree ? "Pega tu key gratis de Groq" : "Key del servidor disponible"} disabled={isRunning} className="w-full" />
                  <a href="https://console.groq.com/keys" target="_blank" rel="noopener" className="text-[11px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key gratis -</a>
                </div>
              )}
              {provider === "gemini" && (
                <div>
                  <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Gemini API Key {isFree && <span className="text-[var(--color-warning)]">*requerido</span>}
                    {hasGeminiKey && <span className="text-[var(--color-success)] ml-1">- guardada</span>}
                  </label>
                  <Input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder={hasGeminiKey ? "Usando key guardada" : isFree ? "Pega tu key gratis de Gemini" : "Key del servidor disponible"} disabled={isRunning} className="w-full" />
                  <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" className="text-[11px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key gratis -</a>
                </div>
              )}
              {PROVIDERS.find((p) => p.value === provider)?.premium && (
                <div>
                  <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    API Key Premium {hasPremiumKey && <span className="text-[var(--color-success)] ml-1">- guardada</span>}
                  </label>
                  <Input type="password" value={premiumKey} onChange={(e) => setPremiumKey(e.target.value)} placeholder={hasPremiumKey ? "Usando key guardada" : "Pega tu API key"} disabled={isRunning} className="w-full" />
                  {provider === "openai" && <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener" className="text-[11px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key -</a>}
                  {provider === "deepseek" && <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener" className="text-[11px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key -</a>}
                  {provider === "mistral" && <a href="https://console.mistral.ai/api-keys" target="_blank" rel="noopener" className="text-[11px] text-[var(--color-accent)] underline hover:opacity-80 mt-1 inline-block">Obténer key -</a>}
                </div>
              )}
              {provider === "omniroute" && (
                <div className="md:col-span-3">
                  <div className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-3">
                    <div className="flex items-start gap-2">
                      <span className="text-[var(--color-success)] text-[14px]">✓</span>
                      <div className="flex-1">
                        <p className="text-[11px] text-[var(--color-text)] font-bold mb-1">
                          OmniRoute — 291 providers de IA, 90+ gratis, auto-fallback + compresion de tokens
                        </p>
                        <p className="text-[11px] text-[var(--color-text-muted)] mb-2">
                          Funciona sin API key (providers free pre-wired). Para usar providers premium (Claude, GPT-4o, etc.),
                          copia tu key del dashboard de OmniRoute.
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[11px] text-[var(--color-text-muted)]">Instalar:</span>
                          <code className="text-[11px] bg-[var(--color-surface)] px-2 py-0.5 rounded-[4px] text-[var(--color-success)]">
                            npm i -g omniroute && omniroute
                          </code>
                          <a href="https://github.com/diegosouzapw/OmniRoute" target="_blank" rel="noopener" className="text-[11px] text-[var(--color-accent)] underline hover:opacity-80">
                            Docs -
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
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
                    <span className="text-[11px] text-[var(--color-text-muted)]">No compra en bajista</span>
                  </label>
                </Tooltip>
                <Tooltip text="Confirma con timeframe mayor (2h) antes de comprar en 1h. Reduce falsas entradas.">
                  <label className="flex items-center gap-2 rounded-[8px] bg-[var(--color-surface-2)] p-2 cursor-pointer">
                    <input type="checkbox" checked={useMtf} onChange={(e) => setUseMtf(e.target.checked)} disabled={isRunning} className="w-4 h-4 accent-[var(--color-accent)]" />
                    <span className="text-[11px] font-bold text-[var(--color-text)]">MTF Confirm</span>
                    <span className="text-[11px] text-[var(--color-text-muted)]">Confirma 2h trend</span>
                  </label>
                </Tooltip>
                <Tooltip text="Evita comprar símbolos correlacionados con posiciones existentes (ej: no comprar ETH si ya tienes BTC).">
                  <label className="flex items-center gap-2 rounded-[8px] bg-[var(--color-surface-2)] p-2 cursor-pointer">
                    <input type="checkbox" checked={useCorrelation} onChange={(e) => setUseCorrelation(e.target.checked)} disabled={isRunning} className="w-4 h-4 accent-[var(--color-accent)]" />
                    <span className="text-[11px] font-bold text-[var(--color-text)]">Correlation Filter</span>
                    <span className="text-[11px] text-[var(--color-text-muted)]">Diversificación real</span>
                  </label>
                </Tooltip>
              </div>

              {/* Whitelist / Blacklist */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <MultiSymbolSelector
                  label="Lista Blanca (solo estos símbolos)"
                  description="Si pones símbolos, la IA SOLO podrá tocar esos. Vacío = todos."
                  value={whitelist}
                  onChange={setWhitelist}
                  symbols={aiSymbols}
                  loading={aiSymbolsLoading}
                  disabled={isRunning}
                  quoteAsset={aiQuoteAsset}
                  onQuoteChange={setAiQuoteAsset}
                  quoteAssets={aiQuoteAssets}
                  pickerOpen={whitelistPickerOpen}
                  setPickerOpen={setWhitelistPickerOpen}
                  search={whitelistSearch}
                  setSearch={setWhitelistSearch}
                />
                <MultiSymbolSelector
                  label="Lista Negra (nunca tocar)"
                  description="La IA nunca comprará estos símbolos."
                  value={blacklist}
                  onChange={setBlacklist}
                  symbols={aiSymbols}
                  loading={aiSymbolsLoading}
                  disabled={isRunning}
                  quoteAsset={aiQuoteAsset}
                  onQuoteChange={setAiQuoteAsset}
                  quoteAssets={aiQuoteAssets}
                  pickerOpen={blacklistPickerOpen}
                  setPickerOpen={setBlacklistPickerOpen}
                  search={blacklistSearch}
                  setSearch={setBlacklistSearch}
                />
              </div>

              {/* Nivel 3: Custom Instructions */}
              <div className="mt-3">
                <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
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
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
                  La IA leerá estas reglas en cada ciclo y las respetará. Máx 1000 caracteres.
                </p>
              </div>

              {/* Fase 1: Short Trading + Leverage */}
              <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">⚡ Trading Avanzado</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Tooltip text="Permite a la IA hacer SHORTS (vender en mercado bajista). La IA abre posición short cuando detecta sobrecompra + tendencia bajista. Rentable cuando el precio baja.">
                    <label className="flex items-center gap-2 rounded-[8px] bg-[var(--color-surface-2)] p-2.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={shortsEnabled}
                        onChange={(e) => setShortsEnabled(e.target.checked)}
                        disabled={isRunning}
                        className="w-4 h-4 accent-[var(--color-danger)]"
                      />
                      <div>
                        <span className="text-[11px] font-bold text-[var(--color-text)]">🔻 Permitir Shorts</span>
                        <span className="block text-[11px] text-[var(--color-text-muted)]">IA puede ganar en mercado bajista</span>
                      </div>
                    </label>
                  </Tooltip>
                  <Tooltip text="Leverage (apalancamiento) para futures. 1x = sin apalancamiento. Mayor leverage = mayor riesgo y mayor recompensa. Máx 10x.">
                    <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-bold text-[var(--color-text)]">Leverage</span>
                        <span className="text-[13px] font-bold text-[var(--color-accent)]">{leverage}x</span>
                      </div>
                      <input
                        type="range"
                        min={1}
                        max={10}
                        step={1}
                        value={leverage}
                        onChange={(e) => setLeverage(Number(e.target.value))}
                        disabled={isRunning || !shortsEnabled}
                        className="w-full accent-[var(--color-accent)]"
                      />
                      <div className="flex justify-between text-[11px] text-[var(--color-text-muted)] mt-0.5">
                        <span>1x</span><span>5x</span><span>10x</span>
                      </div>
                    </div>
                  </Tooltip>
                </div>
                {shortsEnabled && leverage > 3 && (
                  <p className="text-[11px] text-[var(--color-warning)] mt-1.5">
                    ⚠️ Leverage {leverage}x es alto. Una subida del {(100/leverage).toFixed(1)}% del precio puede liquidar tu posición short.
                  </p>
                )}
              </div>

              <Button variant="primary" size="sm" onClick={saveSymbolSettings} disabled={isRunning}>
                Guardar Filtros
              </Button>
            </div>
          </div>
        )}
    </Card>
  );
}

// ─── Performance Tab ───
function AgentPerformanceTab(props: any) {
  const {
    stats, cycles, cumulativePnl, totalTrades, winRate, totalPnl, openPositions,
    wins, losses, decisionsWithActions, decisionsHold,
    perfData, learningInsights, backtestData, backtestDays, setBacktestDays,
  } = props;

  return (
    <div className="space-y-4">
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
          <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{wins} ganadas / {losses} pérdidas</div>
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
            <span className="text-[11px] text-[var(--color-text-muted)] ml-1">act/hold</span>
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
                <div className="text-[11px] text-[var(--color-text-muted)]">
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
          <h3 className="text-[14px] font-bold text-[var(--color-accent)] mb-3 flex items-center gap-2"><GraduationCap size={16} /> Aprendizaje de la IA — Que estrategias funcionan mejor</h3>
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
                <div className="text-[11px] text-[var(--color-text-muted)]">{data.total} operaciones</div>
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

      {/* Nivel 3: Learning Insights avanzado — evolución + recomendaciones */}
      {learningInsights && learningInsights.status === "ok" && (
        <Card>
          <h3 className="text-[14px] font-bold text-[var(--color-accent)] mb-3 flex items-center gap-2"><BrainCircuit size={16} /> IA Aprende de sus errores — Insights avanzados</h3>

          {/* Summary */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5 text-center">
              <div className="text-[11px] text-[var(--color-text-muted)]">Win Rate General</div>
              <div className={cn(
                "text-[16px] font-bold",
                learningInsights.overall_win_rate >= 0.6 ? "text-[var(--color-success)]" :
                learningInsights.overall_win_rate >= 0.4 ? "text-[var(--color-warning)]" : "text-[var(--color-danger)]"
              )}>
                {(learningInsights.overall_win_rate * 100).toFixed(0)}%
              </div>
            </div>
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5 text-center">
              <div className="text-[11px] text-[var(--color-text-muted)]">Operaciones</div>
              <div className="text-[16px] font-bold text-[var(--color-text)]">{learningInsights.total_records}</div>
            </div>
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5 text-center">
              <div className="text-[11px] text-[var(--color-text-muted)]">Aciertos</div>
              <div className="text-[16px] font-bold text-[var(--color-success)]">{learningInsights.total_correct}</div>
            </div>
          </div>

          {/* Weekly evolution chart */}
          {learningInsights.weekly_evolution && learningInsights.weekly_evolution.length > 1 && (
            <div className="mb-3">
              <div className="text-[11px] font-bold text-[var(--color-text)] mb-2">📈 Evolución semanal del win rate</div>
              <div className="flex items-end gap-1 h-20 bg-[var(--color-surface-2)] rounded-[8px] p-2">
                {learningInsights.weekly_evolution.map((week: any, i: number) => (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end h-full" title={`${week.week}: ${(week.win_rate * 100).toFixed(0)}% (${week.total} ops)`}>
                    <div
                      className={cn(
                        "w-full rounded-t-[2px] min-h-[2px]",
                        week.win_rate >= 0.6 ? "bg-[var(--color-success)]" :
                        week.win_rate >= 0.4 ? "bg-[var(--color-warning)]" : "bg-[var(--color-danger)]"
                      )}
                      style={{ height: `${week.win_rate * 100}%` }}
                    />
                    <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 truncate w-full text-center">{week.week.split("-")[1]}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Best factors */}
          {learningInsights.best_factors && Object.keys(learningInsights.best_factors).length > 0 && (
            <div className="mb-3">
              <div className="text-[11px] font-bold text-[var(--color-success)] mb-1.5">✅ Factores que funcionaron (priorizar)</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(learningInsights.best_factors).slice(0, 5).map(([factor, data]: [string, any]) => (
                  <span key={factor} className="rounded-[6px] bg-[var(--color-success)]/10 text-[var(--color-success)] px-2 py-1 text-[11px] font-bold">
                    {factor}: {(data.win_rate * 100).toFixed(0)}% ({data.total})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Worst factors */}
          {learningInsights.worst_factors && Object.keys(learningInsights.worst_factors).length > 0 && (
            <div className="mb-3">
              <div className="text-[11px] font-bold text-[var(--color-danger)] mb-1.5">❌ Factores que fallaron (evitar)</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(learningInsights.worst_factors).slice(0, 5).map(([factor, data]: [string, any]) => (
                  <span key={factor} className="rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)] px-2 py-1 text-[11px] font-bold">
                    {factor}: {(data.win_rate * 100).toFixed(0)}% ({data.total})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {learningInsights.recommendations && learningInsights.recommendations.length > 0 && (
            <div>
              <div className="text-[11px] font-bold text-[var(--color-text)] mb-1.5 flex items-center gap-1"><Lightbulb size={12} /> Recomendaciones (inyectadas en el prompt de la IA)</div>
              <div className="space-y-1">
                {learningInsights.recommendations.map((rec: string, i: number) => (
                  <div key={i} className="text-[11px] text-[var(--color-text-muted)] bg-[var(--color-surface-2)] rounded-[6px] p-2">
                    {rec}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Nivel 3: AI vs Backtest Comparison */}
      {backtestData && backtestData.status === "ok" && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[14px] font-bold text-[var(--color-accent)] flex items-center gap-2"><BarChart3 size={16} /> IA vs Buy & Hold BTC — Últimos {backtestData.days} días</h3>
            <div className="flex gap-1">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setBacktestDays(d)}
                  className={cn(
                    "px-2 py-0.5 rounded-[6px] text-[11px] font-bold transition-colors",
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
              <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">🤖 AI Agent</div>
              <div className={cn(
                "text-[20px] font-bold",
                backtestData.ai_agent.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                {backtestData.ai_agent.pnl_pct >= 0 ? "+" : ""}{backtestData.ai_agent.pnl_pct}%
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)] mt-1">
                ${backtestData.ai_agent.total_pnl} PnL · {backtestData.ai_agent.total_trades} trades
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)]">
                Win rate: {backtestData.ai_agent.win_rate}% · Avg: ${backtestData.ai_agent.avg_trade}
              </div>
            </div>

            {/* Buy & Hold BTC */}
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3">
              <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">📈 Buy & Hold BTC</div>
              <div className={cn(
                "text-[20px] font-bold",
                backtestData.buy_hold_btc.pnl_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                {backtestData.buy_hold_btc.pnl_pct >= 0 ? "+" : ""}{backtestData.buy_hold_btc.pnl_pct}%
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)] mt-1">
                ${backtestData.buy_hold_btc.pnl_usd} PnL · mismo capital
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)]">
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
            <div className="flex gap-3 mt-2 text-[11px]">
              <span className="text-[var(--color-success)]">Mejor: +{backtestData.ai_agent.best_trade_pct}%</span>
              <span className="text-[var(--color-danger)]">Peor: {backtestData.ai_agent.worst_trade_pct}%</span>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

// ─── Reasoning Tab ───
function AgentReasoningTab({ decisions }: { decisions: any[] }) {
  if (decisions.length === 0) {
    return (
      <Card>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <BrainCircuit size={32} className="text-[var(--color-text-muted)] mb-2" />
          <p className="text-[13px] text-[var(--color-text-muted)]">
            Aún no hay decisiones de la IA para mostrar.
          </p>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
            Activa el asistente para empezar a ver su razonamiento.
          </p>
        </div>
      </Card>
    );
  }
  return (
    <Card>
      <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
        <BrainCircuit size={16} className="text-[var(--color-accent)]" />
        Razonamiento de la IA — Últimas Decisiones
      </h3>
      <div className="space-y-3 max-h-[600px] overflow-y-auto">
        {decisions.slice(0, 20).map((d, i) => (
          <ReasoningCard key={i} entry={d} defaultExpanded={i < 3} />
        ))}
      </div>
    </Card>
  );
}

// ─── Activity Tab ───
function AgentActivityTab({ isRunning, activityLog }: { isRunning: boolean; activityLog: any[] }) {
  return (
    <Card>
      <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3 flex items-center gap-2">
        {isRunning && <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] animate-pulse" />}
        <Activity size={16} className="text-[var(--color-accent)]" />
        Actividad en Tiempo Real
      </h3>
      <div className="bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)] p-3 max-h-[500px] overflow-y-auto font-mono text-[11px] space-y-0.5">
        {activityLog.length === 0 ? (
          <p className="text-[var(--color-text-muted)] text-center py-8 text-[12px]">
            Activa el asistente para ver su actividad en tiempo real.
          </p>
        ) : (
          activityLog.map((entry, i) => {
            const time = entry.timestamp ? fmtTime(entry.timestamp) : "";
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
  const time = entry.timestamp ? fmtDateTime(entry.timestamp) : "";
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
            "text-[11px] font-bold px-2 h-5 rounded flex items-center",
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
                "text-[11px] font-bold px-2 h-5 rounded flex items-center gap-1",
                a.type === "buy" ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
              )}>
                <CryptoIcon symbol={a.symbol} size={12} />
                {a.type === "buy" ? "BUY" : "SELL"} {a.symbol}
                {a.confidence && <span className="ml-1 opacity-60">{Math.round(a.confidence * 100)}%</span>}
              </span>
            ))
          ) : (
            <span className="text-[11px] font-bold text-[var(--color-text-muted)]">HOLD</span>
          )}
          <span className="text-[11px] text-[var(--color-text-muted)]">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>
      {expanded && (
        <div className="mt-3 space-y-2">
          {entry.market_overview && (
            <div>
              <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Market Overview</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.market_overview}</p>
            </div>
          )}
          {entry.analysis && (
            <div>
              <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Analysis</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.analysis}</p>
            </div>
          )}
          {entry.risk_assessment && (
            <div>
              <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Risk Assessment</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.risk_assessment}</p>
            </div>
          )}
          {actions.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Actions</span>
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
                      <span className="text-[11px] font-bold text-[var(--color-accent)]">
                        {Math.round(a.confidence * 100)}% confidence
                      </span>
                    )}
                    {a.stop_loss_pct && (
                      <span className="text-[11px] text-[var(--color-danger)]">SL: {a.stop_loss_pct}%</span>
                    )}
                    {a.take_profit_pct && (
                      <span className="text-[11px] text-[var(--color-success)]">TP: {a.take_profit_pct}%</span>
                    )}
                  </div>
                  {a.reason && <p className="text-[11px] text-[var(--color-text-muted)]">{a.reason}</p>}
                </div>
              ))}
            </div>
          )}
          {entry.next_steps && (
            <div>
              <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Next Steps</span>
              <p className="text-[12px] text-[var(--color-text)] mt-0.5">{entry.next_steps}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
