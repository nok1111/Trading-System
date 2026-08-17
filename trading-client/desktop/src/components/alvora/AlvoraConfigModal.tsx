import { useEffect, useState, useCallback } from "react";
import { X, Settings, Plus, Trash2, ChevronUp, ChevronDown, Check, AlertTriangle, Loader2, Zap, ExternalLink } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { toast } from "../ui/Toast";
import {
  alvoraGetConfig,
  alvoraSaveConfig,
  alvoraTestProvider,
  alvoraTestChain,
  type AlvoraFullConfig,
  type FallbackProviderEntry,
  type TestProviderResult,
} from "../../lib/alvoraApi";

const ALVORA_CONFIG_CACHE_KEY = "alvora_config_cache";

const PROVIDERS = [
  { value: "gemini", label: "Gemini (Google) — Gratis", needsKey: true, defaultModel: "gemini-flash-latest", keyUrl: "https://aistudio.google.com/apikey", keyLabel: "aistudio.google.com/apikey" },
  { value: "groq", label: "Groq (Cloud) — Gratis", needsKey: true, defaultModel: "openai/gpt-oss-120b", keyUrl: "https://console.groq.com/keys", keyLabel: "console.groq.com/keys" },
  { value: "omniroute", label: "OmniRoute (Gateway) — Gratis", needsKey: false, defaultModel: "default", keyUrl: "", keyLabel: "" },
  { value: "ollama", label: "Ollama (Local) — Gratis", needsKey: false, defaultModel: "qwen2.5:14b", keyUrl: "https://ollama.com/download", keyLabel: "ollama.com/download" },
  { value: "openai", label: "OpenAI (GPT-4o) — Premium", needsKey: true, defaultModel: "gpt-4o-mini", keyUrl: "https://platform.openai.com/api-keys", keyLabel: "platform.openai.com/api-keys" },
  { value: "deepseek", label: "DeepSeek — Premium", needsKey: true, defaultModel: "deepseek-chat", keyUrl: "https://platform.deepseek.com/api_keys", keyLabel: "platform.deepseek.com/api_keys" },
  { value: "mistral", label: "Mistral AI — Premium", needsKey: true, defaultModel: "mistral-small-latest", keyUrl: "https://console.mistral.ai/api-keys", keyLabel: "console.mistral.ai/api-keys" },
  { value: "together", label: "Together AI — Premium", needsKey: true, defaultModel: "meta-llama/Llama-3.3-70B-Instruct-Turbo", keyUrl: "https://api.together.xyz/settings/api-keys", keyLabel: "api.together.xyz/settings/api-keys" },
  { value: "perplexity", label: "Perplexity — Premium", needsKey: true, defaultModel: "llama-3.1-sonar-small-128k-online", keyUrl: "https://www.perplexity.ai/settings/api", keyLabel: "perplexity.ai/settings/api" },
  { value: "grok", label: "Grok (xAI) — Premium", needsKey: true, defaultModel: "grok-2-latest", keyUrl: "https://console.x.ai", keyLabel: "console.x.ai" },
];

function getProviderMeta(value: string) {
  return PROVIDERS.find((p) => p.value === value) || PROVIDERS[0];
}

// ─── Provider row (reusable for primary + fallback) ─────────────────────────

function ProviderRow({
  label,
  provider,
  apiKey,
  apiKeySet,
  model,
  onProviderChange,
  onApiKeyChange,
  onModelChange,
  onTest,
  testResult,
  testing,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  label: string;
  provider: string;
  apiKey: string;
  apiKeySet: boolean;
  model: string;
  onProviderChange: (v: string) => void;
  onApiKeyChange: (v: string) => void;
  onModelChange: (v: string) => void;
  onTest: () => void;
  testResult: TestProviderResult | null;
  testing: boolean;
  onRemove?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}) {
  const meta = getProviderMeta(provider);
  return (
    <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{label}</span>
        <div className="flex items-center gap-1">
          {onMoveUp && (
            <button onClick={onMoveUp} className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
              <ChevronUp size={14} />
            </button>
          )}
          {onMoveDown && (
            <button onClick={onMoveDown} className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
              <ChevronDown size={14} />
            </button>
          )}
          {onRemove && (
            <button onClick={onRemove} className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-danger)] hover:bg-[var(--color-surface-hover)]">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">Proveedor</label>
          <select
            value={provider}
            onChange={(e) => onProviderChange(e.target.value)}
            className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">Modelo</label>
          <input
            type="text"
            value={model}
            onChange={(e) => onModelChange(e.target.value)}
            placeholder={meta.defaultModel}
            className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
          />
        </div>
      </div>
      {meta.needsKey && (
        <div>
          <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">
            API Key {apiKeySet && !apiKey && <span className="text-[var(--color-success)]">(guardada)</span>}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            placeholder={apiKeySet ? "•••••••• (dejar vacio para mantener)" : "Pega tu API key"}
            className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
          />
          {meta.keyUrl && (
            <a
              href={meta.keyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-1 text-[10px] font-semibold text-[var(--color-primary)] hover:underline"
            >
              <ExternalLink size={10} />
              Obtener API key: {meta.keyLabel}
            </a>
          )}
        </div>
      )}
      {!meta.needsKey && meta.keyUrl && (
        <a
          href={meta.keyUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--color-primary)] hover:underline"
        >
          <ExternalLink size={10} />
          {meta.keyLabel}
        </a>
      )}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="default" onClick={onTest} disabled={testing} className="!text-[11px]">
          {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
          Test
        </Button>
        {testResult && (
          <span className={cn("text-[11px] font-semibold flex items-center gap-1", testResult.ok ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
            {testResult.ok ? <Check size={12} /> : <AlertTriangle size={12} />}
            {testResult.ok ? `OK — ${testResult.model || "conectado"}` : testResult.error || "Error"}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Toggle switch ───────────────────────────────────────────────────────────

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center justify-between cursor-pointer py-1.5">
      <span className="text-[12px] text-[var(--color-text)]">{label}</span>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={cn(
          "relative w-9 h-5 rounded-full transition-colors flex-shrink-0",
          checked ? "bg-[var(--color-primary)]" : "bg-[var(--color-surface-hover)]"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5"
          )}
        />
      </button>
    </label>
  );
}

// ─── Main modal ──────────────────────────────────────────────────────────────

export function AlvoraConfigModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [config, setConfig] = useState<AlvoraFullConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Primary provider editable fields
  const [primaryApiKey, setPrimaryApiKey] = useState("");
  // Fallback chain editable fields
  const [fallbacks, setFallbacks] = useState<Array<{ provider: string; api_key: string; model: string }>>([]);
  // Test results
  const [primaryTest, setPrimaryTest] = useState<TestProviderResult | null>(null);
  const [primaryTesting, setPrimaryTesting] = useState(false);
  const [fbTests, setFbTests] = useState<Array<TestProviderResult | null>>([]);
  const [fbTesting, setFbTesting] = useState<Array<boolean>>([]);
  const [chainTesting, setChainTesting] = useState(false);
  const [chainResult, setChainResult] = useState<any>(null);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      // Try localStorage cache first for instant load
      const cached = localStorage.getItem(ALVORA_CONFIG_CACHE_KEY);
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          setConfig(parsed);
          setFallbacks(parsed.fallback_chain?.map((f: FallbackProviderEntry) => ({
            provider: f.provider,
            api_key: "",
            model: f.model || "",
          })) || []);
        } catch {}
      }
      // Then fetch from server (source of truth)
      const cfg = await alvoraGetConfig();
      setConfig(cfg);
      setFallbacks(cfg.fallback_chain?.map((f) => ({
        provider: f.provider,
        api_key: "",
        model: f.model || "",
      })) || []);
      setFbTests(new Array(cfg.fallback_chain?.length || 0).fill(null));
      setFbTesting(new Array(cfg.fallback_chain?.length || 0).fill(false));
      // Cache locally
      localStorage.setItem(ALVORA_CONFIG_CACHE_KEY, JSON.stringify(cfg));
    } catch (e: any) {
      toast("Error cargando configuracion: " + e.message, false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadConfig();
  }, [open, loadConfig]);

  if (!open) return null;

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const payload = {
        provider: config.provider,
        api_key: primaryApiKey || null,
        model: config.model || null,
        fallback_chain: fallbacks.map((f) => ({
          provider: f.provider,
          api_key: f.api_key || null,
          model: f.model || null,
        })),
        language: config.language,
        response_style: config.response_style,
        risk_advice_level: config.risk_advice_level,
        auto_suggest_actions: config.auto_suggest_actions,
        max_tokens: config.max_tokens,
        temperature: config.temperature,
        include_positions: config.include_positions,
        include_market_data: config.include_market_data,
        include_profile: config.include_profile,
        include_recommendations: config.include_recommendations,
      };
      const r = await alvoraSaveConfig(payload);
      setConfig(r.config);
      setPrimaryApiKey("");
      // Update localStorage cache
      localStorage.setItem(ALVORA_CONFIG_CACHE_KEY, JSON.stringify(r.config));
      toast("Configuracion de Alvora guardada");
    } catch (e: any) {
      toast("Error guardando: " + e.message, false);
    } finally {
      setSaving(false);
    }
  };

  const handleTestPrimary = async () => {
    if (!config) return;
    setPrimaryTesting(true);
    setPrimaryTest(null);
    try {
      const r = await alvoraTestProvider(config.provider, primaryApiKey || undefined, config.model || undefined);
      setPrimaryTest(r);
    } catch (e: any) {
      setPrimaryTest({ ok: false, error: e.message });
    } finally {
      setPrimaryTesting(false);
    }
  };

  const handleTestFallback = async (idx: number) => {
    const fb = fallbacks[idx];
    if (!fb) return;
    setFbTesting((prev) => prev.map((v, i) => (i === idx ? true : v)));
    setFbTests((prev) => prev.map((v, i) => (i === idx ? null : v)));
    try {
      const r = await alvoraTestProvider(fb.provider, fb.api_key || undefined, fb.model || undefined);
      setFbTests((prev) => prev.map((v, i) => (i === idx ? r : v)));
    } catch (e: any) {
      setFbTests((prev) => prev.map((v, i) => (i === idx ? { ok: false, error: e.message } : v)));
    } finally {
      setFbTesting((prev) => prev.map((v, i) => (i === idx ? false : v)));
    }
  };

  const handleTestChain = async () => {
    setChainTesting(true);
    setChainResult(null);
    try {
      const r = await alvoraTestChain();
      setChainResult(r);
      if (r.has_working) {
        toast(`${r.working}/${r.total} providers funcionan`);
      } else {
        toast("Ningun provider funciona. Revisa tus API keys.", false);
      }
    } catch (e: any) {
      toast("Error testeando cadena: " + e.message, false);
    } finally {
      setChainTesting(false);
    }
  };

  const addFallback = () => {
    setFallbacks((prev) => [...prev, { provider: "groq", api_key: "", model: "" }]);
    setFbTests((prev) => [...prev, null]);
    setFbTesting((prev) => [...prev, false]);
  };

  const removeFallback = (idx: number) => {
    setFallbacks((prev) => prev.filter((_, i) => i !== idx));
    setFbTests((prev) => prev.filter((_, i) => i !== idx));
    setFbTesting((prev) => prev.filter((_, i) => i !== idx));
  };

  const moveFallback = (idx: number, dir: -1 | 1) => {
    setFallbacks((prev) => {
      const next = [...prev];
      const target = idx + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  };

  const updateConfig = (patch: Partial<AlvoraFullConfig>) => {
    setConfig((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div
        className="bg-[var(--color-bg)] rounded-[16px] border border-[var(--color-border)] shadow-2xl w-full max-w-[560px] max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="flex items-center gap-2">
            <Settings size={18} className="text-[var(--color-primary)]" />
            <h2 className="text-[14px] font-extrabold text-[var(--color-text)]">Configuracion de Alvora</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-[8px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={24} className="animate-spin text-[var(--color-primary)]" />
            </div>
          ) : config ? (
            <>
              {/* ─── Primary provider ─────────────────────────────────── */}
              <div>
                <h3 className="text-[12px] font-bold text-[var(--color-text)] mb-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)]" />
                  Provider principal
                </h3>
                <ProviderRow
                  label="Primario"
                  provider={config.provider}
                  apiKey={primaryApiKey}
                  apiKeySet={config.api_key_set}
                  model={config.model}
                  onProviderChange={(v) => updateConfig({ provider: v })}
                  onApiKeyChange={setPrimaryApiKey}
                  onModelChange={(v) => updateConfig({ model: v })}
                  onTest={handleTestPrimary}
                  testResult={primaryTest}
                  testing={primaryTesting}
                />
              </div>

              {/* ─── Fallback chain ───────────────────────────────────── */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-[12px] font-bold text-[var(--color-text)] flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-warning)]" />
                    Fallback providers ({fallbacks.length})
                  </h3>
                  <div className="flex gap-1.5">
                    <Button size="sm" variant="default" onClick={handleTestChain} disabled={chainTesting} className="!text-[11px]">
                      {chainTesting ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
                      Test all
                    </Button>
                    <Button size="sm" variant="ghost" onClick={addFallback} className="!text-[11px]">
                      <Plus size={12} /> Agregar
                    </Button>
                  </div>
                </div>
                {chainResult && (
                  <div className={cn("mb-2 rounded-[8px] p-2 text-[11px]", chainResult.has_working ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-danger)]/10 text-[var(--color-danger)]")}>
                    {chainResult.working}/{chainResult.total} providers funcionan
                    {chainResult.results.map((r: any, i: number) => (
                      <div key={i} className="mt-1 text-[10px]">
                        {r.ok ? "✓" : "✗"} {r.role}: {r.provider} — {r.ok ? "OK" : r.error}
                      </div>
                    ))}
                  </div>
                )}
                {fallbacks.length === 0 ? (
                  <p className="text-[11px] text-[var(--color-text-muted)] p-3 rounded-[8px] bg-[var(--color-surface)] border border-dashed border-[var(--color-border)]">
                    Sin fallbacks. Si el provider principal falla, Alvora no podra responder.
                    Agrega providers de respaldo para mayor disponibilidad.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {fallbacks.map((fb, idx) => (
                      <ProviderRow
                        key={idx}
                        label={`Fallback ${idx + 1}`}
                        provider={fb.provider}
                        apiKey={fb.api_key}
                        apiKeySet={config.fallback_chain?.[idx]?.api_key_set || false}
                        model={fb.model}
                        onProviderChange={(v) => setFallbacks((prev) => prev.map((f, i) => (i === idx ? { ...f, provider: v } : f)))}
                        onApiKeyChange={(v) => setFallbacks((prev) => prev.map((f, i) => (i === idx ? { ...f, api_key: v } : f)))}
                        onModelChange={(v) => setFallbacks((prev) => prev.map((f, i) => (i === idx ? { ...f, model: v } : f)))}
                        onTest={() => handleTestFallback(idx)}
                        testResult={fbTests[idx]}
                        testing={fbTesting[idx]}
                        onRemove={() => removeFallback(idx)}
                        onMoveUp={idx > 0 ? () => moveFallback(idx, -1) : undefined}
                        onMoveDown={idx < fallbacks.length - 1 ? () => moveFallback(idx, 1) : undefined}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* ─── Persona / behavior ───────────────────────────────── */}
              <div>
                <h3 className="text-[12px] font-bold text-[var(--color-text)] mb-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />
                  Personalidad y comportamiento
                </h3>
                <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-2.5">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">Idioma</label>
                      <select
                        value={config.language}
                        onChange={(e) => updateConfig({ language: e.target.value })}
                        className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      >
                        <option value="es">Espanol</option>
                        <option value="en">Ingles</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">Estilo</label>
                      <select
                        value={config.response_style}
                        onChange={(e) => updateConfig({ response_style: e.target.value })}
                        className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      >
                        <option value="concise">Conciso</option>
                        <option value="detailed">Detallado</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">Nivel de riesgo</label>
                      <select
                        value={config.risk_advice_level}
                        onChange={(e) => updateConfig({ risk_advice_level: e.target.value })}
                        className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                      >
                        <option value="conservative">Conservador</option>
                        <option value="balanced">Balanceado</option>
                        <option value="aggressive">Agresivo</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">Max tokens: {config.max_tokens}</label>
                      <input
                        type="range"
                        min={500}
                        max={4000}
                        step={100}
                        value={config.max_tokens}
                        onChange={(e) => updateConfig({ max_tokens: Number(e.target.value) })}
                        className="w-full mt-1.5"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] mb-0.5">
                      Temperatura (creatividad): {config.temperature.toFixed(1)}
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.1}
                      value={config.temperature}
                      onChange={(e) => updateConfig({ temperature: Number(e.target.value) })}
                      className="w-full mt-1"
                    />
                  </div>
                  <Toggle
                    checked={config.auto_suggest_actions}
                    onChange={(v) => updateConfig({ auto_suggest_actions: v })}
                    label="Sugerir acciones ejecutables (cerrar posiciones, ajustar SL/TP)"
                  />
                </div>
              </div>

              {/* ─── Context inclusion ────────────────────────────────── */}
              <div>
                <h3 className="text-[12px] font-bold text-[var(--color-text)] mb-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)]" />
                  Contexto incluido en respuestas
                </h3>
                <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <Toggle checked={config.include_positions} onChange={(v) => updateConfig({ include_positions: v })} label="Posiciones abiertas" />
                  <Toggle checked={config.include_market_data} onChange={(v) => updateConfig({ include_market_data: v })} label="Datos de mercado (Fear&Greed, dominance)" />
                  <Toggle checked={config.include_profile} onChange={(v) => updateConfig({ include_profile: v })} label="Perfil de riesgo del usuario" />
                  <Toggle checked={config.include_recommendations} onChange={(v) => updateConfig({ include_recommendations: v })} label="Recomendaciones recientes" />
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-[var(--color-text-muted)]">No se pudo cargar la configuracion</div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
          <p className="text-[10px] text-[var(--color-text-muted)]">
            Las API keys se guardan encriptadas localmente. La config persiste al cerrar sesion.
          </p>
          <div className="flex gap-2">
            <Button variant="ghost" size="md" onClick={onClose}>Cancelar</Button>
            <Button variant="primary" size="md" onClick={handleSave} disabled={saving || loading}>
              {saving ? "Guardando..." : "Guardar"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
