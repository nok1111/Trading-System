import { useEffect, useRef, useState, useCallback } from "react";
import { Send, Sparkles, Check, X, AlertTriangle, MessageSquarePlus, Trash2, ChevronDown, Settings } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";
import { toast } from "../ui/Toast";
import {
  alvoraChat,
  alvoraGetMessages,
  alvoraGetQuickPrompts,
  alvoraExecuteAction,
  alvoraDeleteConversation,
  alvoraListConversations,
  alvoraGetStatus,
  alvoraConfigure,
  type AlvoraMessage,
  type AlvoraAction,
  type AlvoraQuickPrompt,
  type AlvoraConversation,
  type AlvoraStatus,
} from "../../lib/alvoraApi";
import { AlvoraConfigModal } from "./AlvoraConfigModal";

interface AlvoraChatProps {
  /** Compact mode for the floating widget (smaller heights, no sidebar) */
  compact?: boolean;
  /** Initial conversation id to load (optional) */
  initialConversationId?: number | null;
  className?: string;
}

// ─── Lightweight markdown renderer (bold, lists, line breaks) ───────────────

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let listItems: React.ReactNode[] = [];

  const flushList = (key: string) => {
    if (listItems.length > 0) {
      nodes.push(
        <ul key={key} className="list-disc pl-4 space-y-0.5 my-1">
          {listItems}
        </ul>
      );
      listItems = [];
    }
  };

  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(
        <li key={`li-${i}`} className="text-[var(--color-text)]">
          {renderInline(trimmed.slice(2))}
        </li>
      );
      return;
    }
    flushList(`ul-${i}`);
    if (trimmed === "") {
      nodes.push(<div key={`br-${i}`} className="h-1.5" />);
    } else {
      nodes.push(
        <p key={`p-${i}`} className="text-[var(--color-text)] leading-relaxed">
          {renderInline(trimmed)}
        </p>
      );
    }
  });
  flushList("ul-end");
  return <>{nodes}</>;
}

function renderInline(text: string): React.ReactNode {
  // Split on **bold** markers
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-bold text-[var(--color-text)]">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

// ─── Action card ────────────────────────────────────────────────────────────

function ActionCard({
  action,
  conversationId,
  onExecuted,
}: {
  action: AlvoraAction;
  conversationId: number | null;
  onExecuted: (result: { status: string; [k: string]: any }) => void;
}) {
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<{ status: string; [k: string]: any } | null>(null);
  const [editableSize, setEditableSize] = useState<string>(
    action.params.position_size_usd ? String(action.params.position_size_usd) : ""
  );
  const [editableSL, setEditableSL] = useState<string>(
    action.params.stop_loss_pct ? String(action.params.stop_loss_pct) : ""
  );
  const [editableTP, setEditableTP] = useState<string>(
    action.params.take_profit_pct ? String(action.params.take_profit_pct) : ""
  );

  const labels: Record<string, string> = {
    close_position: "Cerrar posicion",
    open_trade: "Abrir trade",
    set_stop_loss: "Ajustar Stop-Loss",
    set_take_profit: "Ajustar Take-Profit",
  };

  const handleExecute = async () => {
    setExecuting(true);
    // Build params with edited values
    const finalParams = { ...action.params };
    if (action.params.position_size_usd !== undefined && editableSize) {
      finalParams.position_size_usd = parseFloat(editableSize) as any;
    }
    if (action.params.stop_loss_pct !== undefined && editableSL) {
      finalParams.stop_loss_pct = parseFloat(editableSL) as any;
    }
    if (action.params.take_profit_pct !== undefined && editableTP) {
      finalParams.take_profit_pct = parseFloat(editableTP) as any;
    }
    try {
      const r = await alvoraExecuteAction(action.type, finalParams, conversationId ?? undefined);
      setResult(r);
      onExecuted(r);
      if (r.status === "executed") {
        toast(`${labels[action.type] || action.type} ejecutado`, true);
      } else {
        toast(r.reason || r.status || "No se pudo ejecutar", false);
      }
    } catch (e: any) {
      const err = { status: "error", reason: e.message || "Error" };
      setResult(err);
      onExecuted(err);
      toast(e.message || "Error al ejecutar", false);
    } finally {
      setExecuting(false);
    }
  };

  if (result) {
    const ok = result.status === "executed";
    return (
      <div
        className={cn(
          "mt-2 rounded-[8px] border p-2.5 text-[11px]",
          ok
            ? "border-[var(--color-success)]/40 bg-[var(--color-success)]/10"
            : "border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10"
        )}
      >
        <div className="flex items-center gap-1.5 font-bold">
          {ok ? <Check size={12} className="text-[var(--color-success)]" /> : <AlertTriangle size={12} className="text-[var(--color-danger)]" />}
          <span className={ok ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {ok ? "Ejecutado" : "No ejecutado"}
          </span>
        </div>
        {result.reason && <p className="mt-1 text-[var(--color-text-muted)]">{result.reason}</p>}
        {result.symbol && <p className="mt-0.5 text-[var(--color-text-muted)]">{result.symbol}</p>}
      </div>
    );
  }

  return (
    <div className="mt-2 rounded-[8px] border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/8 p-2.5">
      <div className="flex items-center gap-1.5 mb-1">
        <Sparkles size={12} className="text-[var(--color-primary)]" />
        <span className="text-[11px] font-bold text-[var(--color-primary)]">
          {labels[action.type] || action.type}
        </span>
      </div>
      <div className="text-[11px] text-[var(--color-text-muted)] space-y-0.5 mb-2">
        {action.params.symbol && <div>Symbol: <span className="font-bold text-[var(--color-text)]">{action.params.symbol}</span></div>}
        {action.params.broker_id && <div>Broker: <span className="font-bold text-[var(--color-text)]">{action.params.broker_id}</span></div>}
        {action.params.position_id && <div>Posicion #{action.params.position_id}</div>}
        {action.params.action_type && <div>Tipo: {action.params.action_type}</div>}
        {action.params.stop_loss_pct !== undefined && (
          <div className="flex items-center gap-1.5">
            <span>SL:</span>
            <input
              type="number"
              step="0.1"
              value={editableSL}
              onChange={(e) => setEditableSL(e.target.value)}
              className="w-16 px-1 py-0.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] text-[11px]"
            />
            <span>%</span>
          </div>
        )}
        {action.params.take_profit_pct !== undefined && (
          <div className="flex items-center gap-1.5">
            <span>TP:</span>
            <input
              type="number"
              step="0.1"
              value={editableTP}
              onChange={(e) => setEditableTP(e.target.value)}
              className="w-16 px-1 py-0.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] text-[11px]"
            />
            <span>%</span>
          </div>
        )}
        {action.params.position_size_usd !== undefined && (
          <div className="flex items-center gap-1.5">
            <span>Tamano:</span>
            <div className="flex items-center">
              <span className="text-[var(--color-text-muted)]">$</span>
              <input
                type="number"
                step="1"
                min="1"
                value={editableSize}
                onChange={(e) => setEditableSize(e.target.value)}
                className="w-20 px-1 py-0.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] text-[11px]"
              />
            </div>
          </div>
        )}
        {action.reason && <div className="italic mt-1">{action.reason}</div>}
      </div>
      <div className="flex gap-1.5">
        <Button size="sm" variant="primary" onClick={handleExecute} disabled={executing} className="!text-[11px]">
          {executing ? "Ejecutando..." : "Confirmar"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onExecuted({ status: "dismissed" })} disabled={executing} className="!text-[11px]">
          <X size={12} /> Descartar
        </Button>
      </div>
    </div>
  );
}

// ─── Main chat component ────────────────────────────────────────────────────

export function AlvoraChat({ compact = false, initialConversationId = null, className }: AlvoraChatProps) {
  const [messages, setMessages] = useState<AlvoraMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(initialConversationId);
  const [quickPrompts, setQuickPrompts] = useState<AlvoraQuickPrompt[]>([]);
  const [conversations, setConversations] = useState<AlvoraConversation[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [status, setStatus] = useState<AlvoraStatus | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [cfgProvider, setCfgProvider] = useState("gemini");
  const [cfgApiKey, setCfgApiKey] = useState("");
  const [cfgModel, setCfgModel] = useState("");
  const [cfgSaving, setCfgSaving] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadQuickPrompts = useCallback(async () => {
    try {
      const q = await alvoraGetQuickPrompts();
      setQuickPrompts(q);
    } catch {}
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const s = await alvoraGetStatus();
      setStatus(s);
    } catch {}
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const c = await alvoraListConversations();
      setConversations(c);
    } catch {}
  }, []);

  const loadMessages = useCallback(async (cid: number) => {
    try {
      const m = await alvoraGetMessages(cid);
      setMessages(m);
    } catch {
      setMessages([]);
    }
  }, []);

  useEffect(() => {
    loadQuickPrompts();
    loadConversations();
    loadStatus();
  }, [loadQuickPrompts, loadConversations, loadStatus]);

  useEffect(() => {
    if (initialConversationId) {
      setConversationId(initialConversationId);
      loadMessages(initialConversationId);
    }
  }, [initialConversationId, loadMessages]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const send = async (text: string) => {
    const msg = text.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);

    // Optimistic: add user message immediately
    const optimisticUser: AlvoraMessage = {
      id: -Date.now(),
      role: "user",
      content: msg,
      actions: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);

    try {
      const r = await alvoraChat(msg, conversationId ?? undefined);
      if (r.conversation_id && conversationId === null) {
        setConversationId(r.conversation_id);
      }
      const assistantMsg: AlvoraMessage = {
        id: r.message_id,
        role: "assistant",
        content: r.reply,
        actions: r.actions || [],
        provider: r.provider,
        model: r.model,
        latency_ms: r.latency_ms,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      loadConversations();
    } catch (e: any) {
      const errMsg: AlvoraMessage = {
        id: -Date.now() - 1,
        role: "assistant",
        content: `Error: ${e.message || "No se pudo conectar con Alvora"}`,
        actions: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setConversationId(null);
    setShowHistory(false);
    inputRef.current?.focus();
  };

  const selectConversation = (cid: number) => {
    setConversationId(cid);
    loadMessages(cid);
    setShowHistory(false);
  };

  const handleDeleteConversation = async (cid: number) => {
    try {
      await alvoraDeleteConversation(cid);
      if (conversationId === cid) {
        startNewConversation();
      }
      loadConversations();
      toast("Conversacion eliminada");
    } catch (e: any) {
      toast(e.message || "Error al eliminar", false);
    }
  };

  const saveConfig = async () => {
    setCfgSaving(true);
    try {
      const r = await alvoraConfigure(cfgProvider, cfgApiKey || undefined, cfgModel || undefined);
      if (r.available) {
        toast("Alvora configurado y listo");
        setShowConfig(false);
        setStatus({ available: true, provider: r.provider });
      } else {
        toast("Guardado pero el provider no responde. Verifica tu API key.", false);
      }
      loadStatus();
    } catch (e: any) {
      toast(e.message || "Error al guardar configuracion", false);
    } finally {
      setCfgSaving(false);
    }
  };

  const handleActionExecuted = (msgId: number) => (result: { status: string; [k: string]: any }) => {
    // Mark action as resolved in the message
    if (result.status === "dismissed") {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, actions: m.actions.map((a) => ({ ...a, reason: a.reason + " [descartada]" })) }
            : m
        )
      );
    }
  };

  const hasMessages = messages.length > 0;
  const isEmpty = !hasMessages && !loading;

  return (
    <div className={cn("flex flex-col bg-[var(--color-surface)] rounded-[12px] border border-[var(--color-border)] overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-[8px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center flex-shrink-0">
            <Sparkles size={14} className="text-white" />
          </div>
          <div className="leading-none">
            <div className="text-[13px] font-extrabold text-[var(--color-text)]">Alvora</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">Asesor de trading</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {conversations.length > 0 && (
            <button
              onClick={() => setShowHistory((v) => !v)}
              className="flex items-center gap-1 px-2 h-7 rounded-[6px] text-[11px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
              title="Historial"
            >
              <ChevronDown size={13} className={cn("transition-transform", showHistory && "rotate-180")} />
              Historial
            </button>
          )}
          <button
            onClick={() => setShowConfigModal(true)}
            className="flex items-center justify-center w-7 h-7 rounded-[6px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            title="Configuracion de Alvora"
          >
            <Settings size={14} />
          </button>
          <button
            onClick={startNewConversation}
            className="flex items-center gap-1 px-2 h-7 rounded-[6px] text-[11px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            title="Nueva conversacion"
          >
            <MessageSquarePlus size={13} />
            Nueva
          </button>
        </div>
      </div>

      {/* History dropdown */}
      {showHistory && conversations.length > 0 && (
        <div className="border-b border-[var(--color-border)] bg-[var(--color-surface)] max-h-[200px] overflow-y-auto">
          {conversations.map((c) => (
            <div
              key={c.id}
              className={cn(
                "flex items-center justify-between px-3 py-2 hover:bg-[var(--color-surface-hover)] cursor-pointer group",
                c.id === conversationId && "bg-[var(--color-primary)]/8"
              )}
              onClick={() => selectConversation(c.id)}
            >
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-semibold text-[var(--color-text)] truncate">{c.title}</div>
                <div className="text-[10px] text-[var(--color-text-muted)]">{c.message_count} mensajes</div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleDeleteConversation(c.id); }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-all"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* No API configured warning banner */}
      {status && !status.available && (
        <div className="mx-3 mt-3 rounded-[10px] border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-[var(--color-danger)] flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="text-[12px] font-bold text-[var(--color-danger)] mb-1">
                Alvora no tiene una API de IA configurada
              </div>
              <div className="text-[11px] text-[var(--color-danger)]/90 leading-relaxed space-y-0.5">
                <p>Para usar Alvora necesitas configurar al menos un proveedor de IA. Pasos:</p>
                <ol className="list-decimal pl-4 space-y-0.5 mt-1">
                  <li>Haz clic en el icono de ajustes <Settings size={11} className="inline align-middle" /> en la esquina superior derecha de esta ventana.</li>
                  <li>Selecciona un proveedor (recomendado: <strong>Gemini</strong> o <strong>Groq</strong> — son gratis).</li>
                  <li>Pega tu API key en el campo correspondiente (debajo del campo hay un link directo para obtenerla).</li>
                  <li>Haz clic en <strong>Test</strong> para verificar que funciona.</li>
                  <li>Haz clic en <strong>Guardar</strong> y listo — podras chatear con Alvora.</li>
                </ol>
                <p className="mt-1.5">Tambien puedes configurarlo desde <strong>Settings &gt; Alvora — IA Advisor</strong>.</p>
              </div>
              <button
                onClick={() => setShowConfigModal(true)}
                className="mt-2 inline-flex items-center gap-1.5 px-3 h-7 rounded-[8px] bg-[var(--color-danger)] text-white text-[11px] font-bold hover:opacity-90 transition-opacity"
              >
                <Settings size={13} />
                Configurar ahora
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
        className={cn("flex-1 overflow-y-auto p-3 space-y-3", compact ? "min-h-[300px]" : "min-h-[400px]")}
      >
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-center py-6">
            <div className="w-12 h-12 rounded-[14px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center mb-3 shadow-lg shadow-[var(--color-primary)]/20">
              <Sparkles size={22} className="text-white" />
            </div>
            <div className="text-[15px] font-extrabold text-[var(--color-text)] mb-1">Hola, soy Alvora</div>
            <div className="text-[12px] text-[var(--color-text-muted)] max-w-[280px] mb-4">
              Tu asesor de trading personal. Preguntame sobre tu portafolio, el mercado, o tus posiciones.
            </div>

            {/* Config panel — shown when provider not available or user clicks "configurar" */}
            {showConfig ? (
              <div className="w-full max-w-[300px] space-y-2 text-left">
                <div>
                  <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Proveedor</label>
                  <select
                    value={cfgProvider}
                    onChange={(e) => setCfgProvider(e.target.value)}
                    className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                  >
                    <option value="gemini">Gemini (Google) - Gratis</option>
                    <option value="groq">Groq (Cloud) - Gratis</option>
                    <option value="omniroute">OmniRoute (Gateway) - Gratis</option>
                    <option value="ollama">Ollama (Local) - Gratis</option>
                    <option value="openai">OpenAI (GPT-4o) - Premium</option>
                    <option value="deepseek">DeepSeek - Premium</option>
                    <option value="mistral">Mistral AI - Premium</option>
                  </select>
                </div>
                {(cfgProvider === "groq" || cfgProvider === "gemini" || cfgProvider === "openai" || cfgProvider === "deepseek" || cfgProvider === "mistral" || cfgProvider === "omniroute") && (
                  <div>
                    <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">API Key</label>
                    <input
                      type="password"
                      value={cfgApiKey}
                      onChange={(e) => setCfgApiKey(e.target.value)}
                      placeholder={cfgProvider === "omniroute" ? "Opcional (free providers sin key)" : "Pega tu API key aqui"}
                      className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                    />
                  </div>
                )}
                <div>
                  <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Modelo (opcional)</label>
                  <input
                    type="text"
                    value={cfgModel}
                    onChange={(e) => setCfgModel(e.target.value)}
                    placeholder="Default del proveedor"
                    className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                  />
                </div>
                <div className="flex gap-2 pt-1">
                  <Button size="sm" variant="primary" onClick={saveConfig} disabled={cfgSaving} className="flex-1">
                    {cfgSaving ? "Guardando..." : "Guardar"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowConfig(false)}>
                    Cancelar
                  </Button>
                </div>
                {cfgProvider === "groq" && (
                  <p className="text-[10px] text-[var(--color-text-muted)]">Obten tu key gratis en console.groq.com</p>
                )}
                {cfgProvider === "gemini" && (
                  <p className="text-[10px] text-[var(--color-text-muted)]">Obten tu key gratis en aistudio.google.com</p>
                )}
              </div>
            ) : status && !status.available ? (
              <div className="space-y-2">
                <div className="text-[12px] text-[var(--color-danger)] font-semibold">
                  Alvora necesita un proveedor de IA configurado
                </div>
                <Button size="sm" variant="primary" onClick={() => setShowConfig(true)}>
                  Configurar ahora
                </Button>
              </div>
            ) : (
              /* Quick prompts — shown when provider is available */
              <div className="flex flex-wrap gap-1.5 justify-center max-w-[340px]">
                {quickPrompts.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => send(q.message)}
                    className="px-2.5 py-1.5 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[11px] font-semibold text-[var(--color-text)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all"
                  >
                    {q.label}
                  </button>
                ))}
                <button
                  onClick={() => setShowConfig(true)}
                  className="px-2.5 py-1.5 rounded-[8px] text-[11px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-all"
                >
                  Configurar proveedor
                </button>
              </div>
            )}
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[85%] rounded-[12px] px-3 py-2",
                m.role === "user"
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface-2)] border border-[var(--color-border)]"
              )}
            >
              <div className="text-[12px] space-y-1">
                {renderMarkdown(m.content)}
              </div>
              {/* Action cards */}
              {m.actions && m.actions.length > 0 && (
                <div className="space-y-1.5">
                  {m.actions.map((a) => (
                    <ActionCard
                      key={a.id}
                      action={a}
                      conversationId={conversationId}
                      onExecuted={handleActionExecuted(m.id)}
                    />
                  ))}
                </div>
              )}
              {/* Provider meta for assistant */}
              {m.role === "assistant" && m.model && (
                <div className="mt-1.5 text-[9px] text-[var(--color-text-muted)] opacity-60">
                  {m.provider} · {m.model} {m.latency_ms ? `· ${m.latency_ms}ms` : ""}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[12px] px-3 py-2.5">
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-[var(--color-border)] p-2.5 bg-[var(--color-surface)]">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Pregunta a Alvora..."
            rows={1}
            className="flex-1 resize-none rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 py-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/15 placeholder:text-[var(--color-text-muted)] transition-all max-h-[100px]"
            style={{ minHeight: "36px" }}
            disabled={loading}
          />
          <Button
            variant="primary"
            size="md"
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="!px-3 flex-shrink-0"
          >
            <Send size={15} />
          </Button>
        </div>
      </div>

      {/* Config modal */}
      <AlvoraConfigModal open={showConfigModal} onClose={() => setShowConfigModal(false)} />
    </div>
  );
}
