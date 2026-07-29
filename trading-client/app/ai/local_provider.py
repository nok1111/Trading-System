"""LocalAIProvider — encapsula toda la logica de proveedores locales de IA.

Extrae la logica que estaba en agent.py:
- Groq (cloud, gratis)
- Gemini (cloud, gratis)
- OpenAI-compatible (OpenAI, DeepSeek, Mistral, Together, Perplexity, Grok)
- Ollama (local)

Cadena de fallback: provider principal -> secundario -> Ollama local.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from app.ai.provider import AIProvider, AIProviderConfig, AIResponse

logger = logging.getLogger(__name__)


class LocalAIProvider(AIProvider):
    """Proveedor de IA local con cadena de fallback entre Groq, Gemini, OpenAI-compat y Ollama."""

    def __init__(self, config: AIProviderConfig) -> None:
        self._config = config
        self._provider = config.provider
        self._log: list[str] = []
        self._last_http_error: str | None = None

    def get_name(self) -> str:
        return f"local:{self._provider}"

    def is_available(self) -> bool:
        if self._provider == "groq":
            return bool(self._config.groq_api_key)
        if self._provider == "gemini":
            return bool(self._config.gemini_api_key)
        if self._provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            return bool(self._config.openai_api_key)
        return self._provider == "ollama"

    def ask(self, system_prompt: str, user_message: str) -> AIResponse:
        """Envia el mensaje al proveedor configurado con cadena de fallback."""
        start = time.monotonic()

        if self._provider == "groq":
            result = self._ask_groq(system_prompt, user_message)
            if result is None and self._config.gemini_api_key:
                self._log.append("Groq no disponible, intentando con Gemini...")
                result = self._ask_gemini(system_prompt, user_message)
            if result is None:
                self._log.append("Groq no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message)
        elif self._provider == "gemini":
            result = self._ask_gemini(system_prompt, user_message)
            if result is None and self._config.groq_api_key:
                self._log.append("Gemini no disponible, intentando con Groq...")
                result = self._ask_groq(system_prompt, user_message)
            if result is None:
                self._log.append("Gemini no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message)
        elif self._provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            result = self._ask_openai_compat(system_prompt, user_message)
            if result is None and self._config.groq_api_key:
                self._log.append(f"{self._provider} no disponible, intentando con Groq...")
                result = self._ask_groq(system_prompt, user_message)
            if result is None:
                self._log.append(f"{self._provider} no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message)
        elif self._provider == "ollama":
            result = self._ask_ollama(system_prompt, user_message)
        else:
            return AIResponse(
                decision=None,
                provider_name=self.get_name(),
                model="unknown",
                error=f"Provider desconocido: {self._provider}",
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        model = self._get_model_name()

        if result is None:
            error_msg = f"Ni {self._provider}, fallback ni Ollama disponibles."
            if self._log:
                error_msg += " Logs: " + "; ".join(self._log[-3:])
            if self._last_http_error:
                error_msg += f" Último error HTTP: {self._last_http_error}"
            return AIResponse(
                decision=None,
                provider_name=self.get_name(),
                model=model,
                latency_ms=latency_ms,
                error=error_msg,
            )

        return AIResponse(
            decision=result,
            provider_name=self.get_name(),
            model=model,
            latency_ms=latency_ms,
        )

    def get_logs(self) -> list[str]:
        return list(self._log)

    def get_last_http_error(self) -> str | None:
        return self._last_http_error

    def _get_model_name(self) -> str:
        if self._provider == "groq":
            return self._config.groq_model
        if self._provider == "gemini":
            return self._config.gemini_model
        if self._provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            return self._config.openai_model
        return self._config.ollama_model

    def _ask_groq(self, system_prompt: str, user_msg: str) -> dict | None:
        if not self._config.groq_api_key:
            self._last_http_error = "No hay Groq API key configurada"
            return None
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._config.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._config.groq_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:300] if exc.response.text else ""
            self._last_http_error = f"HTTP {status}: {detail}"
            logger.error(f"Groq API error {status}: {detail}")
            return None
        except Exception as exc:
            self._last_http_error = str(exc)
            logger.error(f"Error consultando Groq: {exc}")
            return None

    def _ask_gemini(self, system_prompt: str, user_msg: str) -> dict | None:
        if not self._config.gemini_api_key:
            self._last_http_error = "No hay Gemini API key configurada"
            return None
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._config.gemini_model}:generateContent?key={self._config.gemini_api_key}"
            resp = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 1000,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_response(content)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:300] if exc.response.text else ""
            self._last_http_error = f"HTTP {status}: {detail}"
            logger.error(f"Gemini API error {status}: {detail}")
            return None
        except Exception as exc:
            self._last_http_error = str(exc)
            logger.error(f"Error consultando Gemini: {exc}")
            return None

    def _ask_openai_compat(self, system_prompt: str, user_msg: str) -> dict | None:
        if not self._config.openai_api_key:
            self._last_http_error = f"No hay API key configurada para {self._provider}"
            return None
        try:
            resp = httpx.post(
                f"{self._config.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._config.openai_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "response_format": {"type": "json_object"},
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:300] if exc.response.text else ""
            self._last_http_error = f"HTTP {status}: {detail}"
            logger.error(f"{self._provider} API error {status}: {detail}")
            return None
        except Exception as exc:
            self._last_http_error = str(exc)
            logger.error(f"Error consultando {self._provider}: {exc}")
            return None

    def _ask_ollama(self, system_prompt: str, user_msg: str) -> dict | None:
        try:
            resp = httpx.post(
                f"{self._config.ollama_url.rstrip('/')}/api/chat",
                json={
                    "model": self._config.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3},
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return self._parse_response(content)
        except Exception as exc:
            logger.error(f"Error consultando Ollama: {exc}")
            return None

    @staticmethod
    def _parse_response(content: str) -> dict | None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    pass
            logger.error(f"Respuesta no es JSON valido: {content[:200]}")
            return None
