import { useEffect, useState, useCallback } from "react";
import { Eye, RefreshCw, ChevronDown, ChevronUp, Cpu, Clock } from "lucide-react";
import { getCopilotContext } from "../../lib/copilotApi";

export function AITransparencyPanel() {
  const [context, setContext] = useState<string>("");
  const [contextLength, setContextLength] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getCopilotContext();
      setContext(result.context);
      setContextLength(result.context_length);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Parse context into sections for display
  const sections = context.split("\n\n").filter((s) => s.trim().length > 0);

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Eye size={16} className="text-[var(--color-text-muted)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Transparencia IA</h3>
        <span className="text-[10px] text-[var(--color-text-muted)]">
          ({contextLength} chars)
        </span>
        <button
          onClick={fetchData}
          className="ml-auto text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1 rounded"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="rounded-lg bg-[var(--color-surface-2)] p-2">
          <div className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)] mb-0.5">
            <Cpu size={10} />
            Contexto
          </div>
          <div className="text-[14px] font-bold text-[var(--color-text)]">
            {sections.length} secciones
          </div>
        </div>
        <div className="rounded-lg bg-[var(--color-surface-2)] p-2">
          <div className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)] mb-0.5">
            <Clock size={10} />
            Tokens aprox.
          </div>
          <div className="text-[14px] font-bold text-[var(--color-text)]">
            ~{Math.ceil(contextLength / 4)}
          </div>
        </div>
      </div>

      {/* Expandable context */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[11px] text-[var(--color-primary)] hover:underline w-full"
      >
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {expanded ? "Ocultar contexto" : "Ver contexto completo"}
      </button>

      {expanded && (
        <div className="mt-2 max-h-[300px] overflow-y-auto rounded-lg bg-[var(--color-surface-2)] p-3 text-[10px] font-mono text-[var(--color-text-muted)] whitespace-pre-wrap break-words">
          {loading ? "Cargando..." : context || "Sin contexto disponible"}
        </div>
      )}

      {/* Privacy note */}
      <div className="mt-3 text-[10px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2">
        La IA solo ve los datos mostrados arriba. No tiene acceso a tus API keys ni secretos.
      </div>
    </div>
  );
}
