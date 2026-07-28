import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { toast } from "../components/ui/Toast";
import { cn } from "../lib/utils";

const PROVIDERS = [
  { value: "gemini", label: "Gemini (Google Cloud) — Gratis" },
  { value: "groq", label: "Groq (Cloud) — Gratis" },
  { value: "ollama", label: "Ollama (Local) — Gratis" },
  { value: "openai", label: "OpenAI (GPT-4o) — Premium", premium: true },
  { value: "deepseek", label: "DeepSeek — Premium", premium: true },
  { value: "mistral", label: "Mistral AI — Premium", premium: true },
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
    { value: "qwen2.5:7b", label: "Qwen 2.5 7B (rápido)" },
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

  useEffect(() => {
    loadStatus();
    loadLog();
    loadStats();
    loadPlan();
    const id1 = setInterval(loadStatus, 3000);
    const id2 = setInterval(loadLog, 3000);
    const id3 = setInterval(loadStats, 10000);
    return () => {
      clearInterval(id1);
      clearInterval(id2);
      clearInterval(id3);
    };
  }, [loadStatus, loadLog, loadStats, loadPlan]);

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
      const body: any = { provider };
      if (groqKey) body.groq_api_key = groqKey;
      if (geminiKey) body.gemini_api_key = geminiKey;
      if (premiumKey) body.premium_api_key = premiumKey;

      const r = await api<any>("/api/ai-agent/test-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setTestResult(r.valid ? "✓ API Key válida" : "✗ API Key inválida");
      toast(r.valid ? "API Key válida" : "API Key inválida", r.valid);
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

  const isRunning = status?.is_running ?? false;
  const decisions = log.filter((e) => e.phase === "decision");
  const activityLog = log.slice(0, 60);

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
      {/* Header with status + controls */}
      <Card className="border-l-4 border-l-[var(--color-accent)]">
        <div className="flex justify-between items-start flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-10 h-10 rounded-[10px] flex items-center justify-center text-[20px]",
              isRunning ? "bg-[var(--color-success)]/15" : "bg-[var(--color-surface-2)]"
            )}>
              {isRunning ? "🤖" : "💤"}
            </div>
            <div>
              <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">AI Trading Agent</h2>
              <p className="text-[12px] text-[var(--color-text-muted)]">
                {isRunning ? (
                  <>
                    <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] mr-1.5 animate-pulse" />
                    Analyzing market · Cycle {cycles} · {status?.model || "AI"}
                  </>
                ) : (
                  "Stopped — click Start to begin"
                )}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="success" onClick={start} disabled={!canStart} className="h-9">▶ Start</Button>
            <Button variant="danger" onClick={stop} disabled={!isRunning} className="h-9">⏹ Stop</Button>
            <Button variant="default" onClick={() => setShowConfig(!showConfig)} className="h-9">⚙ Config</Button>
          </div>
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
            {maxRequestsPerDay === 99999 ? "Unlimited" : `${maxRequestsPerDay} req/day`} · min interval {minInterval}s
          </span>
        </div>

        {/* BYOK notice for FREE users with free providers */}
        {needsByok && !byokReady && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30">
            <p className="text-[12px] font-bold text-[var(--color-warning)]">
              🔑 Bring Your Own Key required for FREE plan
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              {provider === "groq" ? (
                <>Get a free Groq API key at <a href="https://console.groq.com/keys" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline">console.groq.com/keys</a> and paste it in Config below.</>
              ) : (
                <>Get a free Gemini API key at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline">aistudio.google.com/apikey</a> and paste it in Config below.</>
              )}
            </p>
          </div>
        )}

        {/* Premium provider locked for FREE */}
        {isPremiumProvider && isFree && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
            <p className="text-[12px] font-bold text-[var(--color-danger)]">
              🔒 {provider} requires PRO or PREMIUM subscription
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              Upgrade to use premium AI providers, or switch to Groq/Gemini (free) with your own key.
            </p>
          </div>
        )}

        {/* AI Mode selector */}
        <div className="mt-4 flex gap-2 flex-wrap">
          {([
            { value: "conservative", label: "🛡 Conservative", desc: "Fewer trades, tight stops" },
            { value: "balanced", label: "⚖ Balanced", desc: "Mix of swing & momentum" },
            { value: "aggressive", label: "🚀 Aggressive", desc: "More trades, wider stops" },
          ] as const).map((m) => (
            <button
              key={m.value}
              onClick={() => setAiMode(m.value)}
              className={cn(
                "px-3 h-9 rounded-[8px] text-[12px] font-bold transition-all border",
                aiMode === m.value
                  ? "bg-[var(--color-accent)]/15 border-[var(--color-accent)] text-[var(--color-accent)]"
                  : "bg-[var(--color-surface-2)] border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              )}
              title={m.desc}
            >
              {m.label}
            </button>
          ))}
          <div className="flex items-center gap-2 ml-auto">
            <label className="flex items-center gap-2 text-[12px] font-bold cursor-pointer">
              <input type="checkbox" checked={autoTrade} onChange={toggleAutoTrade} className="w-4 h-4 accent-[var(--color-accent)]" />
              <span className="text-[var(--color-accent)]">Auto-trade</span>
            </label>
            <span className={cn(
              "text-[11px] font-bold px-2 h-5 rounded flex items-center",
              tradeMode === "live"
                ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]"
                : "bg-[var(--color-success)]/10 text-[var(--color-success)]"
            )}>
              {tradeMode.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Config panel (collapsible) */}
        {showConfig && (
          <div className="mt-4 pt-4 border-t border-[var(--color-border)] space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Provider</label>
                <Select value={provider} onChange={(e) => { setProvider(e.target.value); const ms = MODELS[e.target.value]; if (ms) setModel(ms[0].value); }} className="w-full">
                  {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Model</label>
                <Select value={model} onChange={(e) => setModel(e.target.value)} className="w-full">
                  {(MODELS[provider] || []).map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Interval (sec)</label>
                <div className="flex gap-1">
                  <Input type="number" value={interval} onChange={(e) => setIntervalVal(parseInt(e.target.value) || 30)} min={10} className="w-20" />
                  <Button variant="primary" size="sm" onClick={setIntervalApi}>Set</Button>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {provider === "groq" && (
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Groq API Key {isFree && <span className="text-[var(--color-warning)]">*required</span>}
                    {hasGroqKey && <span className="text-[var(--color-success)] ml-1">✓ saved</span>}
                  </label>
                  <Input type="password" value={groqKey} onChange={(e) => setGroqKey(e.target.value)} placeholder={hasGroqKey ? "Using saved key" : isFree ? "Paste your free Groq key" : "Server key available"} className="w-full" />
                </div>
              )}
              {provider === "gemini" && (
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Gemini API Key {isFree && <span className="text-[var(--color-warning)]">*required</span>}
                    {hasGeminiKey && <span className="text-[var(--color-success)] ml-1">✓ saved</span>}
                  </label>
                  <Input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder={hasGeminiKey ? "Using saved key" : isFree ? "Paste your free Gemini key" : "Server key available"} className="w-full" />
                </div>
              )}
              {PROVIDERS.find((p) => p.value === provider)?.premium && (
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                    Premium API Key {hasPremiumKey && <span className="text-[var(--color-success)] ml-1">✓ saved</span>}
                  </label>
                  <Input type="password" value={premiumKey} onChange={(e) => setPremiumKey(e.target.value)} placeholder={hasPremiumKey ? "Using saved key" : "Enter your API key"} className="w-full" />
                </div>
              )}
            </div>
            <div className="flex gap-3 items-center flex-wrap">
              <div className="flex gap-2">
                <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--color-border)] cursor-pointer text-[12px] font-bold">
                  <input type="radio" name="tradeMode" checked={tradeMode === "paper"} onChange={() => setTradeMode("paper")} className="accent-[var(--color-success)]" />
                  <span className="text-[var(--color-success)]">Paper</span>
                </label>
                <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--color-border)] cursor-pointer text-[12px] font-bold">
                  <input type="radio" name="tradeMode" checked={tradeMode === "live"} onChange={() => setTradeMode("live")} className="accent-[var(--color-danger)]" />
                  <span className="text-[var(--color-danger)]">Live</span>
                </label>
              </div>
              <Button variant="default" size="sm" onClick={testKey}>Test API Key</Button>
              {testResult && <span className="text-[12px] font-bold">{testResult}</span>}
            </div>
            {tradeMode === "live" && (
              <div className="p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
                <p className="text-[12px] font-bold text-[var(--color-danger)]">⚠️ Live Trading: Orders will execute with real money.</p>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Stats Dashboard */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Card>
          <CardLabel>Total Trades</CardLabel>
          <CardValue className="text-[var(--color-primary)]">{totalTrades}</CardValue>
        </Card>
        <Card>
          <CardLabel>Win Rate</CardLabel>
          <CardValue className={winRate >= 50 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {winRate.toFixed(1)}%
          </CardValue>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">{wins}W / {losses}L</div>
        </Card>
        <Card>
          <CardLabel>Total PnL</CardLabel>
          <CardValue className={totalPnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)} USDT
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Open Positions</CardLabel>
          <CardValue className="text-[var(--color-accent)]">{openPositions}</CardValue>
        </Card>
        <Card>
          <CardLabel>Cycles</CardLabel>
          <CardValue>{cycles}</CardValue>
        </Card>
        <Card>
          <CardLabel>Decisions</CardLabel>
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
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Cumulative PnL (closed trades)</h3>
          <PnlSparkline data={cumulativePnl} />
        </Card>
      )}

      {/* By symbol breakdown */}
      {stats?.by_symbol && Object.keys(stats.by_symbol).length > 0 && (
        <Card>
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Performance by Symbol</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(stats.by_symbol).map(([sym, data]: [string, any]) => (
              <div key={sym} className="rounded-[8px] bg-[var(--color-surface-2)] p-2.5">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] font-bold text-[var(--color-text)]">{sym}</span>
                  <span className={cn(
                    "text-[11px] font-bold",
                    data.pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                  )}>
                    {data.pnl >= 0 ? "+" : ""}{data.pnl.toFixed(2)}
                  </span>
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)]">
                  {data.buys}B / {data.sells}S · {data.wins}W/{data.losses}L
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Reasoning Cards */}
      {decisions.length > 0 && (
        <Card>
          <h3 className="text-[13px] font-bold text-[var(--color-accent)] mb-3">🧠 AI Reasoning — Latest Decisions</h3>
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {decisions.slice(0, 10).map((d, i) => (
              <ReasoningCard key={i} entry={d} />
            ))}
          </div>
        </Card>
      )}

      {/* Activity Feed */}
      <Card>
        <h3 className="text-[13px] font-bold text-[var(--color-accent)] mb-3">
          {isRunning && <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] mr-2 animate-pulse" />}
          Activity Feed — Real Time
        </h3>
        <div className="bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)] p-3 max-h-80 overflow-y-auto font-mono text-[11px] space-y-0.5">
          {activityLog.length === 0 ? (
            <p className="text-[var(--color-text-muted)] text-center py-8 text-[12px]">
              Start the AI Agent to see its real-time activity.
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

function ReasoningCard({ entry }: { entry: any }) {
  const [expanded, setExpanded] = useState(false);
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
                "text-[10px] font-bold px-2 h-5 rounded flex items-center",
                a.type === "buy" ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
              )}>
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
                      "text-[11px] font-bold",
                      a.type === "buy" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                    )}>
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
