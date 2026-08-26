import { useState, useCallback, useEffect, useRef } from "react";
import {
  copilotChat,
  getCopilotSuggestions,
  type CopilotChatResponse,
  type CopilotSuggestion,
} from "../lib/copilotApi";

interface UseCopilotReturn {
  messages: CopilotMessage[];
  suggestions: CopilotSuggestion[];
  loading: boolean;
  suggestionsLoading: boolean;
  conversationId: number | null;
  error: string | null;
  send: (message: string) => Promise<void>;
  refreshSuggestions: () => Promise<void>;
  clearError: () => void;
}

export interface CopilotMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  actions?: Array<{
    id: string;
    type: string;
    params: Record<string, string>;
    reason: string;
  }>;
  provider?: string;
  model?: string;
  latencyMs?: number;
  timestamp: number;
}

/**
 * Hook para interactuar con el Alvora Copilot.
 * Maneja estado de chat, sugerencias proactivas, y errores.
 */
export function useCopilot(): UseCopilotReturn {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [suggestions, setSuggestions] = useState<CopilotSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const msgIdCounter = useRef(0);

  const send = useCallback(async (message: string) => {
    if (!message.trim() || loading) return;

    setError(null);
    setLoading(true);

    // Add user message immediately
    const userMsg: CopilotMessage = {
      id: --msgIdCounter.current,
      role: "user",
      content: message,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const result: CopilotChatResponse = await copilotChat(message, conversationId ?? undefined);

      if (result.error) {
        setError(result.error);
      }

      if (result.conversation_id) {
        setConversationId(result.conversation_id);
      }

      const assistantMsg: CopilotMessage = {
        id: result.message_id ?? --msgIdCounter.current,
        role: "assistant",
        content: result.reply || "",
        actions: result.actions,
        provider: result.provider,
        model: result.model,
        latencyMs: result.latency_ms,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setError(err.message || "Error al comunicarse con el Copilot");
    } finally {
      setLoading(false);
    }
  }, [loading, conversationId]);

  const refreshSuggestions = useCallback(async () => {
    setSuggestionsLoading(true);
    try {
      const result = await getCopilotSuggestions();
      setSuggestions(result.suggestions);
    } catch {
      // silent — suggestions are non-critical
    } finally {
      setSuggestionsLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  // Fetch suggestions on mount
  useEffect(() => {
    refreshSuggestions();
  }, [refreshSuggestions]);

  return {
    messages,
    suggestions,
    loading,
    suggestionsLoading,
    conversationId,
    error,
    send,
    refreshSuggestions,
    clearError,
  };
}
