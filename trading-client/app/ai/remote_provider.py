"""RemoteAIProvider — stub para gateway de IA remoto (Fase 4).

El gateway remoto recibira el contexto del mercado y devolvera decisiones
de trading sin exponer prompts ni datos sensibles al servidor.

TODO(fase-4): Implementar cuando el gateway remoto este disponible.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.ai.provider import AIProvider, AIProviderConfig, AIResponse, ChatMessage, ChatResponse

logger = logging.getLogger(__name__)


class RemoteAIProvider(AIProvider):
    """Proveedor de IA remoto via gateway HTTP.

    Envia el contexto comprimido al gateway y recibe una decision JSON.
    No envia API keys ni prompts al servidor — solo el contexto del mercado.
    """

    def __init__(self, config: AIProviderConfig) -> None:
        self._config = config
        self._url = config.remote_ai_url or ""
        self._token = config.remote_ai_token

    def get_name(self) -> str:
        return "remote"

    def is_available(self) -> bool:
        return bool(self._url)

    def chat(
        self,
        system_prompt: str,
        messages: list[ChatMessage],
        max_tokens: int = 1500,
        temperature: float = 0.5,
    ) -> ChatResponse:
        """Chat libre via gateway remoto."""
        start = time.monotonic()
        if not self._url:
            return ChatResponse(text="", provider_name=self.get_name(), model="remote-gateway", error="REMOTE_AI_URL no configurado")
        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            resp = httpx.post(
                f"{self._url.rstrip('/')}/v1/ai/chat",
                headers=headers,
                json={
                    "system_prompt": system_prompt,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return ChatResponse(
                text=data.get("text", ""),
                provider_name=self.get_name(),
                model=data.get("model", "remote-gateway"),
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as exc:
            logger.error(f"Remote AI chat error: {exc}")
            return ChatResponse(
                text="",
                provider_name=self.get_name(),
                model="remote-gateway",
                latency_ms=int((time.monotonic() - start) * 1000),
                error=str(exc),
            )

    def ask(self, system_prompt: str, user_message: str) -> AIResponse:
        start = time.monotonic()

        if not self._url:
            return AIResponse(
                decision=None,
                provider_name=self.get_name(),
                model="remote-gateway",
                error="REMOTE_AI_URL no configurado",
            )

        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            resp = httpx.post(
                f"{self._url.rstrip('/')}/v1/ai/decide",
                headers=headers,
                json={
                    "context": user_message,
                    "system_prompt": system_prompt,
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            data = resp.json()
            latency_ms = int((time.monotonic() - start) * 1000)

            return AIResponse(
                decision=data.get("decision"),
                provider_name=self.get_name(),
                model=data.get("model", "remote-gateway"),
                latency_ms=latency_ms,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(f"Remote AI error {exc.response.status_code}: {exc.response.text[:200]}")
            return AIResponse(
                decision=None,
                provider_name=self.get_name(),
                model="remote-gateway",
                latency_ms=int((time.monotonic() - start) * 1000),
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            logger.error(f"Error consultando Remote AI: {exc}")
            return AIResponse(
                decision=None,
                provider_name=self.get_name(),
                model="remote-gateway",
                latency_ms=int((time.monotonic() - start) * 1000),
                error=str(exc),
            )
