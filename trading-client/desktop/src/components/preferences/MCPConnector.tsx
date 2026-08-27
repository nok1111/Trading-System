import { useEffect, useState, useCallback } from "react";
import { Plug, Check, AlertTriangle, Loader2, Copy, RefreshCw, Terminal } from "lucide-react";
import { cn } from "../../lib/utils";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { toast } from "../ui/Toast";
import {
  getMcpConfig,
  startMcpSession,
  closeMcpSession,
  type McpConfigResponse,
  type McpSessionResponse,
} from "../../lib/defiApi";

export function MCPConnector() {
  const [config, setConfig] = useState<McpConfigResponse | null>(null);
  const [session, setSession] = useState<McpSessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const cfg = await getMcpConfig();
      setConfig(cfg);
    } catch {
      // silent fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleGenerateToken = async () => {
    setGenerating(true);
    try {
      const result = await startMcpSession();
      setSession(result);
      toast("Token MCP generado", true);
      // Reload config with the new session token
      loadConfig();
    } catch (e: any) {
      toast("Error: " + e.message, false);
    } finally {
      setGenerating(false);
    }
  };

  const handleCloseSession = async () => {
    try {
      await closeMcpSession();
      setSession(null);
      toast("Sesion cerrada", true);
    } catch (e: any) {
      toast("Error: " + e.message, false);
    }
  };

  const handleCopy = () => {
    if (!config?.config_json) return;
    navigator.clipboard.writeText(config.config_json).then(() => {
      setCopied(true);
      toast("Config copiado al portapapeles", true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const tools = config?.tools || [];
  const isConnected = !!session || !!config;

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center">
            <Plug size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-primary)]">MCP Connector</h3>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
              Conecta Claude, ChatGPT o Cursor a tu plataforma de trading
            </p>
          </div>
        </div>
        <Badge variant={isConnected ? "success" : "default"}>
          {isConnected ? <Check size={10} /> : <AlertTriangle size={10} />}
          {isConnected ? "Conectado" : "No conectado"}
        </Badge>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 size={20} className="animate-spin text-[var(--color-primary)]" />
        </div>
      ) : (
        <div className="space-y-3">
          {/* Connection status */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1">Estado</div>
              <div className={cn("text-[13px] font-semibold flex items-center gap-1", isConnected ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]")}>
                {isConnected ? <Check size={14} /> : <AlertTriangle size={14} />}
                {isConnected ? "Activo" : "Inactivo"}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1">Herramientas</div>
              <div className="text-[13px] font-semibold text-[var(--color-text)]">
                {config?.tool_count || 0} tools
              </div>
            </div>
          </div>

          {/* Session info */}
          {session && (
            <div className="rounded-lg bg-[var(--color-success)]/10 border border-[var(--color-success)]/20 p-2.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-[var(--color-text-muted)]">Token MCP</span>
                <span className="font-mono text-[10px] text-[var(--color-success)] truncate max-w-[180px]">
                  {session.token.substring(0, 16)}...
                </span>
              </div>
              <div className="flex items-center justify-between text-[11px] mt-1">
                <span className="text-[var(--color-text-muted)]">Expira en</span>
                <span className="font-semibold">{session.expires_in}s</span>
              </div>
            </div>
          )}

          {/* Generate token button */}
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={handleGenerateToken} disabled={generating}>
              {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              Generar nuevo token MCP
            </Button>
            {session && (
              <Button variant="ghost" size="sm" onClick={handleCloseSession}>
                Cerrar sesion
              </Button>
            )}
          </div>

          {/* Config JSON */}
          {config?.config_json && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">
                  Config JSON
                </div>
                <Button variant="ghost" size="sm" onClick={handleCopy}>
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  {copied ? "Copiado" : "Copiar"}
                </Button>
              </div>
              <textarea
                readOnly
                value={config.config_json}
                className="w-full h-[180px] px-3 py-2 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] text-[11px] font-mono resize-none outline-none focus:border-[var(--color-primary)]"
                onClick={(e) => e.currentTarget.select()}
              />
            </div>
          )}

          {/* Tools list */}
          {tools.length > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1.5">
                Herramientas disponibles
              </div>
              <div className="flex flex-wrap gap-1">
                {tools.map((tool) => (
                  <span
                    key={tool}
                    className="px-2 py-0.5 rounded-md bg-[var(--color-surface-2)] text-[10px] font-mono text-[var(--color-text-muted)]"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Instructions */}
          <div className="rounded-lg bg-[var(--color-surface-2)] p-3 space-y-2">
            <div className="flex items-center gap-1.5">
              <Terminal size={12} className="text-[var(--color-primary)]" />
              <span className="text-[11px] font-bold text-[var(--color-text)]">Instrucciones</span>
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] space-y-1">
              <p><span className="font-semibold text-[var(--color-text)]">Claude Desktop:</span> Pega el config JSON en Settings → Developer → MCP Servers.</p>
              <p><span className="font-semibold text-[var(--color-text)]">ChatGPT:</span> Usa el config en Settings → Tools → MCP.</p>
              <p><span className="font-semibold text-[var(--color-text)]">Cursor:</span> Pega el config en Settings → MCP → Add Server.</p>
            </div>
          </div>

          <p className="text-[10px] text-[var(--color-text-muted)]">
            Las API keys nunca se exponen — solo se retornan resultados. El token MCP tiene una validez de 1 hora.
          </p>
        </div>
      )}
    </Card>
  );
}
