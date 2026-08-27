import { useState, useRef, useEffect } from "react";
import { Send, Bot } from "lucide-react";
import { api } from "../../lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface AITutorProps {
  tutorialContext?: string;
}

export function AITutor({ tutorialContext }: AITutorProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hola! Soy tu tutor de AI de Alvora Academy. Puedes preguntarme sobre cualquier tutorial, concepto de trading, o estrategia. ¿En qué puedo ayudarte?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const contextPrefix = tutorialContext
        ? `I'm currently studying the tutorial: ${tutorialContext}. `
        : "";
      const result = await api<{ reply?: string; response?: string }>("/api/copilot/chat", {
        method: "POST",
        body: JSON.stringify({
          message: contextPrefix + userMessage,
        }),
      });
      const reply = result.reply || result.response || "Lo siento, no pude procesar tu pregunta en este momento.";
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "No pude conectar con el AI en este momento. Asegúrate de estar autenticado y de que el servidor esté disponible. Mientras tanto, puedes seguir revisando los tutoriales.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="panel flex flex-col" style={{ height: "500px" }}>
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b border-[var(--color-border)] flex-shrink-0">
        <Bot size={16} className="text-[var(--color-primary)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">AI Tutor</h3>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-semibold">
          Ask anything
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div
              className={`flex items-center justify-center w-7 h-7 rounded-full flex-shrink-0 ${
                msg.role === "user"
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-primary)]"
              }`}
            >
              {msg.role === "user" ? (
                <span className="text-[10px] font-bold">You</span>
              ) : (
                <Bot size={14} />
              )}
            </div>
            <div
              className={`max-w-[80%] px-3 py-2 rounded-xl text-[13px] leading-relaxed ${
                msg.role === "user"
                  ? "bg-[var(--color-primary)] text-white rounded-tr-sm"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text)] rounded-tl-sm"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[var(--color-surface-2)] text-[var(--color-primary)] flex-shrink-0">
              <Bot size={14} />
            </div>
            <div className="bg-[var(--color-surface-2)] px-3 py-2 rounded-xl rounded-tl-sm">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-[var(--color-text-muted)] animate-pulse" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 rounded-full bg-[var(--color-text-muted)] animate-pulse" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 rounded-full bg-[var(--color-text-muted)] animate-pulse" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-[var(--color-border)] flex-shrink-0">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about any tutorial or concept..."
            disabled={loading}
            className="flex-1 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[13px] text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="p-2 rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
