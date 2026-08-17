import { useEffect, useState, useCallback } from "react";
import { Settings, Check, AlertTriangle, Loader2, Zap } from "lucide-react";
import { cn } from "../../lib/utils";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { toast } from "../ui/Toast";
import { AlvoraConfigModal } from "../alvora/AlvoraConfigModal";
import {
  alvoraGetConfig,
  alvoraTestChain,
  type AlvoraFullConfig,
  type TestChainResult,
} from "../../lib/alvoraApi";

const PROVIDER_LABELS: Record<string, string> = {
  gemini: "Gemini",
  groq: "Groq",
  omniroute: "OmniRoute",
  ollama: "Ollama",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  mistral: "Mistral",
  together: "Together AI",
  perplexity: "Perplexity",
  grok: "Grok",
};

export function AlvoraSettingsSection() {
  const [config, setConfig] = useState<AlvoraFullConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [chainTesting, setChainTesting] = useState(false);
  const [chainResult, setChainResult] = useState<TestChainResult | null>(null);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const cfg = await alvoraGetConfig();
      setConfig(cfg);
    } catch (e: any) {
      // silent fail — settings page should still load
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // Reload config when modal closes (in case it was saved)
  useEffect(() => {
    if (!showModal) loadConfig();
  }, [showModal, loadConfig]);

  const handleTestChain = async () => {
    setChainTesting(true);
    setChainResult(null);
    try {
      const r = await alvoraTestChain();
      setChainResult(r);
      if (r.has_working) {
        toast(`${r.working}/${r.total} providers funcionan`, true);
      } else {
        toast("Ningun provider funciona. Configura tus API keys.", false);
      }
    } catch (e: any) {
      toast("Error: " + e.message, false);
    } finally {
      setChainTesting(false);
    }
  };

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center">
            <Settings size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-primary)]">Alvora — IA Advisor</h3>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Configuracion del asesor conversacional</p>
          </div>
        </div>
        <Button variant="primary" size="sm" onClick={() => setShowModal(true)}>
          <Settings size={14} /> Configurar
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 size={20} className="animate-spin text-[var(--color-primary)]" />
        </div>
      ) : config ? (
        <div className="space-y-3">
          {/* Primary provider status */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1">Provider</div>
              <div className="text-[13px] font-semibold text-[var(--color-text)]">
                {PROVIDER_LABELS[config.provider] || config.provider}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1">Modelo</div>
              <div className="text-[13px] font-semibold text-[var(--color-text)] truncate">
                {config.model || "default"}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1">API Key</div>
              <div className={cn("text-[13px] font-semibold flex items-center gap-1", config.api_key_set ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]")}>
                {config.api_key_set ? <Check size={14} /> : <AlertTriangle size={14} />}
                {config.api_key_set ? "Configurada" : "No configurada"}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1">Fallbacks</div>
              <div className="text-[13px] font-semibold text-[var(--color-text)]">
                {config.fallback_chain?.length || 0} providers
              </div>
            </div>
          </div>

          {/* Persona summary */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            <span className="px-2 py-0.5 rounded-md bg-[var(--color-surface-2)] text-[10px] font-semibold text-[var(--color-text-muted)]">
              Idioma: {config.language === "es" ? "Espanol" : "Ingles"}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-[var(--color-surface-2)] text-[10px] font-semibold text-[var(--color-text-muted)]">
              Estilo: {config.response_style === "concise" ? "Conciso" : "Detallado"}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-[var(--color-surface-2)] text-[10px] font-semibold text-[var(--color-text-muted)]">
              Riesgo: {config.risk_advice_level}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-[var(--color-surface-2)] text-[10px] font-semibold text-[var(--color-text-muted)]">
              Tokens: {config.max_tokens}
            </span>
            <span className="px-2 py-0.5 rounded-md bg-[var(--color-surface-2)] text-[10px] font-semibold text-[var(--color-text-muted)]">
              Temp: {config.temperature.toFixed(1)}
            </span>
            {config.auto_suggest_actions && (
              <span className="px-2 py-0.5 rounded-md bg-[var(--color-primary)]/15 text-[10px] font-semibold text-[var(--color-primary)]">
                Acciones auto
              </span>
            )}
          </div>

          {/* Test chain button + results */}
          <div className="flex items-center gap-2 pt-1">
            <Button variant="default" size="sm" onClick={handleTestChain} disabled={chainTesting}>
              {chainTesting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              Test all providers
            </Button>
            {chainResult && (
              <span className={cn("text-[12px] font-semibold", chainResult.has_working ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                {chainResult.working}/{chainResult.total} funcionando
              </span>
            )}
          </div>

          {/* Fallback chain detail */}
          {config.fallback_chain && config.fallback_chain.length > 0 && (
            <div className="pt-2">
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1.5">Cadena de fallback</div>
              <div className="flex flex-wrap items-center gap-1">
                <span className="px-2 py-1 rounded-md bg-[var(--color-primary)]/15 text-[11px] font-bold text-[var(--color-primary)]">
                  1. {PROVIDER_LABELS[config.provider] || config.provider}
                </span>
                {config.fallback_chain.map((f, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span className="text-[var(--color-text-muted)] text-[10px]">→</span>
                    <span className="px-2 py-1 rounded-md bg-[var(--color-surface-2)] text-[11px] font-semibold text-[var(--color-text)]">
                      {i + 2}. {PROVIDER_LABELS[f.provider] || f.provider}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] text-[var(--color-text-muted)] pt-1">
            Las API keys se guardan encriptadas localmente en el servidor.
            La configuracion persiste al cerrar sesion y reiniciar el sistema.
          </p>
        </div>
      ) : (
        <div className="text-center py-6 text-[var(--color-text-muted)] text-sm">
          No se pudo cargar la configuracion.
          <br />
          <Button variant="default" size="sm" className="mt-2" onClick={loadConfig}>Reintentar</Button>
        </div>
      )}

      {/* Config modal */}
      <AlvoraConfigModal open={showModal} onClose={() => setShowModal(false)} />
    </Card>
  );
}
