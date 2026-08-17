"""Interfaz abstracta AIProvider para desacoplar el agente de los proveedores de IA.

Permite intercambiar entre proveedores locales (Groq, Gemini, Ollama, OpenAI-compat)
y un gateway remoto (Fase 4) sin modificar agent.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIProviderConfig:
    """Configuracion inmutable para un proveedor de IA."""

    provider: str = "groq"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    # OmniRoute — AI Gateway local (291 providers, 90+ free, auto-fallback)
    omniroute_url: str = "http://localhost:20128/v1"
    omniroute_api_key: str | None = None
    omniroute_model: str = "auto"
    remote_ai_url: str | None = None
    remote_ai_token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIResponse:
    """Respuesta normalizada de un proveedor de IA."""

    decision: dict | None
    provider_name: str
    model: str
    latency_ms: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.decision is not None and self.error is None


@dataclass(frozen=True)
class ChatMessage:
    """Mensaje de conversacion (para el metodo chat)."""
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass(frozen=True)
class ChatResponse:
    """Respuesta de chat (texto libre, no JSON)."""
    text: str
    provider_name: str
    model: str
    latency_ms: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.text is not None and self.error is None


class AIProvider(ABC):
    """Interfaz para proveedores de IA.

    Metodos:
        ask: Envia system_prompt + user_message y devuelve AIResponse (JSON).
        chat: Conversacion libre con historial, devuelve ChatResponse (texto).
        get_name: Devuelve el nombre del proveedor para logging.
        is_available: Verifica si el proveedor esta configurado.
    """

    @abstractmethod
    def ask(self, system_prompt: str, user_message: str) -> AIResponse:
        """Envia un mensaje al proveedor de IA y devuelve la respuesta normalizada (JSON)."""

    def chat(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        max_tokens: int = 1500,
        temperature: float = 0.5,
    ) -> ChatResponse:
        """Conversacion libre con historial. Devuelve texto (no JSON).

        Implementacion por defecto: convierte a ask() con el ultimo mensaje.
        Los providers deben sobreescribir para soporte real de historial.
        """
        last = messages[-1] if messages else ChatMessage(role="user", content="")
        resp = self.ask(system_prompt, last.content)
        if resp.success and resp.decision is not None:
            import json as _json
            text = _json.dumps(resp.decision, ensure_ascii=False, indent=2)
        else:
            text = resp.error or "Sin respuesta"
        return ChatResponse(
            text=text,
            provider_name=self.get_name(),
            model=resp.model,
            latency_ms=resp.latency_ms,
            error=resp.error,
        )

    @abstractmethod
    def get_name(self) -> str:
        """Devuelve el nombre del proveedor."""

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el proveedor esta configurado y disponible."""
