import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
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
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash (rápido)" },
    { value: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite" },
    { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro (potente)" },
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
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("gemini-2.0-flash");
  const [interval, setIntervalVal] = useState(30);
  const [tradeMode, setTradeMode] = useState<"paper" | "live">("paper");
  const [autoTrade, setAutoTrade] = useState(true);
  const [groqKey, setGroqKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [premiumKey, setPremiumKey] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const s = await api<any>("/api/ai-agent/status");
      setStatus(s);
    } catch {}
  }, []);

  const loadLog = useCallback(async () => {
    try {
      const l = await api<any[]>("/api/ai-agent/log");
      setLog(l.slice(-50).reverse());
    } catch {}
  }, []);

  useEffect(() => {
    loadStatus();
    loadLog();
    const id1 = setInterval(loadStatus, 2000);
    const id2 = setInterval(loadLog, 2000);
    return () => {
      clearInterval(id1);
      clearInterval(id2);
    };
  }, [loadStatus, loadLog]);

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
    } catch (e: any) {
      toast(e.message, false);
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
      await api(
        `/api/ai-agent/interval?interval_seconds=${interval}`,
        { method: "PATCH" }
      );
      toast("Intervalo actualizado");
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const toggleAutoTrade = async () => {
    const newVal = !autoTrade;
    setAutoTrade(newVal);
    try {
      await api(
        `/api/ai-agent/auto-trade?enabled=${newVal}`,
        { method: "PATCH" }
      );
      toast(`Auto-trade ${newVal ? "activado" : "desactivado"}`);
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const isRunning = status?.is_running ?? false;

  return (
    <div className="p-5 space-y-4">
      {/* Control panel */}
      <Card className="border-l-4 border-l-[var(--color-accent)]">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-lg font-bold text-[var(--color-accent)]">
              AI Agent — Configuración
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              Configura el proveedor de IA y el modo de trading.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="success"
              onClick={start}
              disabled={isRunning}
            >
              Activar IA
            </Button>
            <Button
              variant="danger"
              onClick={stop}
              disabled={!isRunning}
            >
              Desactivar IA
            </Button>
          </div>
        </div>

        {/* Config grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">
              Proveedor de IA
            </label>
            <Select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                const models = MODELS[e.target.value];
                if (models) setModel(models[0].value);
              }}
              className="w-full"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">
              Modelo
            </label>
            <Select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full"
            >
              {(MODELS[provider] || []).map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">
              Intervalo (seg)
            </label>
            <div className="flex gap-2">
              <Input
                type="number"
                value={interval}
                onChange={(e) =>
                  setIntervalVal(parseInt(e.target.value) || 30)
                }
                min={10}
                className="w-20"
              />
              <Button variant="primary" size="sm" onClick={setIntervalApi}>
                Aplicar
              </Button>
            </div>
          </div>
        </div>

        {/* API keys */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {provider === "groq" && (
            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">
                Groq API Key
              </label>
              <Input
                type="password"
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
                placeholder="Configurada en .env"
                className="w-full"
              />
            </div>
          )}
          {provider === "gemini" && (
            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">
                Gemini API Key
              </label>
              <Input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="Configurada en .env"
                className="w-full"
              />
            </div>
          )}
          {PROVIDERS.find((p) => p.value === provider)?.premium && (
            <div>
              <label className="block text-xs font-semibold text-[var(--color-text-muted)] mb-1.5">
                Premium API Key
              </label>
              <Input
                type="password"
                value={premiumKey}
                onChange={(e) => setPremiumKey(e.target.value)}
                placeholder="Ingresa tu API key"
                className="w-full"
              />
            </div>
          )}
        </div>

        {/* Trade mode + auto-trade */}
        <div className="flex gap-4 items-center flex-wrap">
          <div className="flex gap-2">
            <label className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--color-border)] cursor-pointer text-sm">
              <input
                type="radio"
                name="tradeMode"
                checked={tradeMode === "paper"}
                onChange={() => setTradeMode("paper")}
                className="accent-[var(--color-success)]"
              />
              <span className="text-[var(--color-success)]">Paper</span>
            </label>
            <label className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--color-border)] cursor-pointer text-sm">
              <input
                type="radio"
                name="tradeMode"
                checked={tradeMode === "live"}
                onChange={() => setTradeMode("live")}
                className="accent-[var(--color-danger)]"
              />
              <span className="text-[var(--color-danger)]">Live</span>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={autoTrade}
              onChange={toggleAutoTrade}
              className="w-4 h-4 accent-[var(--color-accent)]"
            />
            <span className="text-[var(--color-accent)]">Auto-trade</span>
          </label>
          <Button
            variant="default"
            size="sm"
            onClick={testKey}
          >
            Probar API Key
          </Button>
          {testResult && (
            <span className="text-sm">{testResult}</span>
          )}
        </div>

        {tradeMode === "live" && (
          <div className="mt-3 p-3 rounded-lg bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30">
            <p className="text-sm text-[var(--color-danger)]">
              ⚠️ <b>Live Trading:</b> Las órdenes se ejecutarán con dinero real.
            </p>
          </div>
        )}
      </Card>

      {/* Status cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-5 gap-3">
        <Card>
          <CardLabel>Estado</CardLabel>
          <CardValue>
            <Badge variant={isRunning ? "success" : "default"}>
              {isRunning ? "Running" : "Detenido"}
            </Badge>
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Provider</CardLabel>
          <CardValue className="text-sm">
            {status?.provider || "--"}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Modelo</CardLabel>
          <CardValue className="text-sm">
            {status?.model || "--"}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Ciclos</CardLabel>
          <CardValue className="text-[var(--color-primary)]">
            {status?.cycles ?? 0}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Decisiones</CardLabel>
          <CardValue className="text-[var(--color-accent)]">
            {status?.total_decisions ?? 0}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Modo</CardLabel>
          <CardValue
            className={
              status?.trade_mode === "live"
                ? "text-[var(--color-danger)]"
                : "text-[var(--color-success)]"
            }
          >
            {(status?.trade_mode || "paper").toUpperCase()}
          </CardValue>
        </Card>
      </div>

      {/* Live feed */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-accent)] mb-3">
          {isRunning && (
            <span className="inline-block w-2 h-2 rounded-full bg-[var(--color-success)] mr-2 animate-pulse" />
          )}
          Feed del Agente IA — Tiempo Real
        </h3>
        <div className="bg-[var(--color-bg)] rounded-lg border border-[var(--color-border)] p-4 max-h-96 overflow-y-auto font-mono text-xs space-y-1">
          {log.length === 0 ? (
            <p className="text-[var(--color-text-muted)] text-center py-8">
              Activa el agente IA para ver su comunicación en tiempo real.
            </p>
          ) : (
            log.map((entry, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-[var(--color-text-muted)]">
                  {entry.timestamp || ""}
                </span>
                <span
                  className={cn(
                    entry.action === "BUY" &&
                      "text-[var(--color-success)]",
                    entry.action === "SELL" &&
                      "text-[var(--color-danger)]",
                    entry.action === "HOLD" &&
                      "text-[var(--color-text-muted)]",
                    !entry.action && "text-[var(--color-accent)]"
                  )}
                >
                  {entry.action || "INFO"}: {entry.message || entry.symbol || ""}
                </span>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
