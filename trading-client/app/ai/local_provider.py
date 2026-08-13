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

    # Default models per premium provider (loaded from config)
    @property
    def PROVIDER_DEFAULTS(self) -> dict[str, dict]:
        from app.config import get_settings
        return get_settings().get_provider_defaults()

    def __init__(self, config: AIProviderConfig) -> None:
        self._config = config
        self._provider = config.provider
        self._log: list[str] = []
        self._last_http_error: str | None = None
        self._effective_model: str | None = None  # Override model if needed

    def get_name(self) -> str:
        return f"local:{self._provider}"

    def is_available(self) -> bool:
        if self._provider == "groq":
            return bool(self._config.groq_api_key)
        if self._provider == "gemini":
            return bool(self._config.gemini_api_key)
        if self._provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            return bool(self._config.openai_api_key)
        if self._provider == "omniroute":
            # OmniRoute works without API key (free providers pre-wired)
            return True
        return self._provider == "ollama"

    def ask(self, system_prompt: str, user_message: str, deep: bool = False) -> AIResponse:
        """Envia el mensaje al proveedor configurado con cadena de fallback.

        Args:
            deep: If True, uses higher max_tokens and longer timeout for deep analysis tasks.
        """
        start = time.monotonic()
        max_tokens = 4000 if deep else 1000
        timeout = 120.0 if deep else 30.0
        # Fallback timeouts are shorter to bound total time per position
        fallback_timeout = 60.0 if deep else 20.0
        ollama_timeout = 30.0 if deep else 15.0

        if self._provider == "groq":
            result = self._ask_groq(system_prompt, user_message, max_tokens=max_tokens, timeout=timeout)
            if result is None and self._config.gemini_api_key:
                self._log.append("Groq no disponible, intentando con Gemini...")
                result = self._ask_gemini(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append("Groq no disponible, intentando con OmniRoute...")
                result = self._ask_omniroute(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append("Groq no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message, timeout=ollama_timeout)
        elif self._provider == "gemini":
            result = self._ask_gemini(system_prompt, user_message, max_tokens=max_tokens, timeout=timeout)
            if result is None and self._config.groq_api_key:
                self._log.append("Gemini no disponible, intentando con Groq...")
                result = self._ask_groq(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append("Gemini no disponible, intentando con OmniRoute...")
                result = self._ask_omniroute(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append("Gemini no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message, timeout=ollama_timeout)
        elif self._provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            # Ensure correct model for this provider
            self._ensure_provider_model()
            result = self._ask_openai_compat(system_prompt, user_message, max_tokens=max_tokens, timeout=timeout)
            if result is None and self._config.groq_api_key:
                self._log.append(f"{self._provider} no disponible, intentando con Groq...")
                result = self._ask_groq(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append(f"{self._provider} no disponible, intentando con OmniRoute...")
                result = self._ask_omniroute(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append(f"{self._provider} no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message, timeout=ollama_timeout)
        elif self._provider == "omniroute":
            # OmniRoute gateway — 291 providers, 90+ free, auto-fallback + compression built-in
            result = self._ask_omniroute(system_prompt, user_message, max_tokens=max_tokens, timeout=timeout)
            if result is None and self._config.groq_api_key:
                self._log.append("OmniRoute no disponible, intentando con Groq...")
                result = self._ask_groq(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None and self._config.gemini_api_key:
                self._log.append("OmniRoute no disponible, intentando con Gemini...")
                result = self._ask_gemini(system_prompt, user_message, max_tokens=max_tokens, timeout=fallback_timeout)
            if result is None:
                self._log.append("OmniRoute no disponible, intentando con Ollama local...")
                result = self._ask_ollama(system_prompt, user_message, timeout=ollama_timeout)
        elif self._provider == "ollama":
            result = self._ask_ollama(system_prompt, user_message, timeout=timeout)
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

    def _ensure_provider_model(self) -> None:
        """Ensure the openai_model is correct for the selected premium provider.

        Prevents sending e.g. 'gemini-2.0-flash' to Mistral's API.
        """
        defaults = self.PROVIDER_DEFAULTS.get(self._provider)
        if not defaults:
            return
        current_model = self._effective_model or self._config.openai_model
        # If model is empty or clearly belongs to another provider, use default
        if not current_model or current_model in (
            "gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro",
            "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "gpt-4o-mini",
        ):
            self._effective_model = defaults["model"]
            logger.info(f"Auto-set model to {defaults['model']} for {self._provider}")
        else:
            self._effective_model = current_model

    def _get_model_name(self) -> str:
        if self._provider == "groq":
            return self._config.groq_model
        if self._provider == "gemini":
            return self._config.gemini_model
        if self._provider in ("openai", "deepseek", "mistral", "together", "perplexity", "grok"):
            return self._effective_model or self._config.openai_model
        if self._provider == "omniroute":
            return f"omniroute:{self._config.omniroute_model}"
        return self._config.ollama_model

    def _ask_groq(self, system_prompt: str, user_msg: str, max_tokens: int = 1000, timeout: float = 30.0) -> dict | None:
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
                    "temperature": 0.4,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
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

    def _ask_gemini(self, system_prompt: str, user_msg: str, max_tokens: int = 1000, timeout: float = 30.0) -> dict | None:
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
                        "temperature": 0.4,
                        "maxOutputTokens": max_tokens,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=timeout,
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

    def _ask_openai_compat(self, system_prompt: str, user_msg: str, max_tokens: int = 1000, timeout: float = 45.0) -> dict | None:
        if not self._config.openai_api_key:
            self._last_http_error = f"No hay API key configurada para {self._provider}"
            return None
        model = self._effective_model or self._config.openai_model
        try:
            resp = httpx.post(
                f"{self._config.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.4,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
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

    def _ask_omniroute(self, system_prompt: str, user_msg: str, max_tokens: int = 1000, timeout: float = 45.0) -> dict | None:
        """Consulta OmniRoute gateway (OpenAI-compatible endpoint).

        OmniRoute agrega 291 providers con auto-fallback, compresion de tokens
        (15-95%) y 19 estrategias de routing. Funciona sin API key (providers
        free pre-wired) o con key del dashboard para providers premium.

        Model 'auto' = smart routing (zero-config).
        """
        url = self._config.omniroute_url.rstrip("/")
        api_key = self._config.omniroute_api_key or "omniroute"  # OmniRoute accepts any non-empty key for free providers
        model = self._config.omniroute_model or "auto"
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload: dict = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.4,
                "max_tokens": max_tokens,
                "stream": False,
                "response_format": {"type": "json_object"},
            }
            resp = httpx.post(
                f"{url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = exc.response.text[:300] if exc.response.text else ""
            self._last_http_error = f"OmniRoute HTTP {status}: {detail}"
            logger.error(f"OmniRoute API error {status}: {detail}")
            return None
        except httpx.ConnectError as exc:
            self._last_http_error = f"OmniRoute no responde en {url}: {exc}"
            logger.error(f"OmniRoute no disponible en {url}. Instala con: npm i -g omniroute && omniroute")
            return None
        except Exception as exc:
            self._last_http_error = str(exc)
            logger.error(f"Error consultando OmniRoute: {exc}")
            return None

    def _ask_ollama(self, system_prompt: str, user_msg: str, timeout: float = 60.0) -> dict | None:
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
                    "options": {"temperature": 0.4},
                },
                timeout=timeout,
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
