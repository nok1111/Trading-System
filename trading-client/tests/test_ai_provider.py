"""Tests para AIProvider — LocalAIProvider y RemoteAIProvider.

Sin red: monkeypatch de httpx.post.
"""

import json
from unittest.mock import MagicMock, patch

from app.ai.local_provider import LocalAIProvider
from app.ai.provider import AIProviderConfig, AIResponse
from app.ai.remote_provider import RemoteAIProvider


class TestAIProviderConfig:
    def test_defaults(self):
        config = AIProviderConfig()
        assert config.provider == "groq"
        assert config.groq_model == "llama-3.3-70b-versatile"
        assert config.ollama_url == "http://localhost:11434"

    def test_custom(self):
        config = AIProviderConfig(provider="ollama", ollama_model="qwen2.5:14b")
        assert config.provider == "ollama"
        assert config.ollama_model == "qwen2.5:14b"


class TestAIResponse:
    def test_success(self):
        resp = AIResponse(decision={"actions": []}, provider_name="local:groq", model="llama-3.1-8b-instant")
        assert resp.success
        assert resp.decision == {"actions": []}

    def test_failure(self):
        resp = AIResponse(decision=None, provider_name="local:groq", model="llama-3.1-8b-instant", error="timeout")
        assert not resp.success
        assert resp.error == "timeout"


class TestLocalAIProvider:
    def _mock_response(self, content: str, status_code: int = 200):
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = {"choices": [{"message": {"content": content}}]}
        mock.raise_for_status = MagicMock()
        if status_code >= 400:
            mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return mock

    def test_get_name(self):
        config = AIProviderConfig(provider="groq", groq_api_key="test-key")
        provider = LocalAIProvider(config)
        assert provider.get_name() == "local:groq"

    def test_is_available_groq(self):
        config = AIProviderConfig(provider="groq", groq_api_key="test-key")
        provider = LocalAIProvider(config)
        assert provider.is_available()

    def test_not_available_groq(self):
        config = AIProviderConfig(provider="groq", groq_api_key=None)
        provider = LocalAIProvider(config)
        assert not provider.is_available()

    def test_is_available_ollama(self):
        config = AIProviderConfig(provider="ollama")
        provider = LocalAIProvider(config)
        assert provider.is_available()

    def test_ask_groq_success(self):
        config = AIProviderConfig(provider="groq", groq_api_key="test-key")
        provider = LocalAIProvider(config)
        decision = {"actions": [{"type": "buy", "symbol": "BTCUSDT"}]}
        mock_resp = self._mock_response(json.dumps(decision))
        with patch("app.ai.local_provider.httpx.post", return_value=mock_resp):
            result = provider.ask("system prompt", "user message")
        assert result.success
        assert result.decision == decision
        assert result.provider_name == "local:groq"

    def test_ask_groq_fallback_to_ollama(self):
        config = AIProviderConfig(provider="groq", groq_api_key="test-key")
        provider = LocalAIProvider(config)
        decision = {"actions": []}

        groq_resp = MagicMock()
        groq_resp.status_code = 500
        groq_resp.raise_for_status.side_effect = Exception("HTTP 500")

        # OmniRoute esta entre Groq y Ollama en la cadena de fallback
        omniroute_resp = MagicMock()
        omniroute_resp.status_code = 500
        omniroute_resp.raise_for_status.side_effect = Exception("HTTP 500")

        ollama_resp = MagicMock()
        ollama_resp.status_code = 200
        ollama_resp.json.return_value = {"message": {"content": json.dumps(decision)}}
        ollama_resp.raise_for_status = MagicMock()

        with patch("app.ai.local_provider.httpx.post", side_effect=[groq_resp, omniroute_resp, ollama_resp]):
            result = provider.ask("system prompt", "user message")
        assert result.success
        assert result.decision == decision
        assert "Groq no disponible" in provider.get_logs()[0]

    def test_ask_all_fail(self):
        config = AIProviderConfig(provider="groq", groq_api_key="test-key")
        provider = LocalAIProvider(config)

        with patch("app.ai.local_provider.httpx.post", side_effect=Exception("connection error")):
            result = provider.ask("system prompt", "user message")
        assert not result.success
        assert result.decision is None
        assert result.error is not None

    def test_ask_unknown_provider(self):
        config = AIProviderConfig(provider="unknown")
        provider = LocalAIProvider(config)
        result = provider.ask("system prompt", "user message")
        assert not result.success
        assert "Provider desconocido" in result.error

    def test_parse_json_from_text(self):
        config = AIProviderConfig(provider="groq", groq_api_key="test-key")
        provider = LocalAIProvider(config)
        decision = {"actions": []}
        content = f"Here is my analysis:\n{json.dumps(decision)}\nDone."
        mock_resp = self._mock_response(content)
        with patch("app.ai.local_provider.httpx.post", return_value=mock_resp):
            result = provider.ask("system prompt", "user message")
        assert result.success
        assert result.decision == decision


class TestRemoteAIProvider:
    def test_get_name(self):
        config = AIProviderConfig(remote_ai_url="https://ai.example.com")
        provider = RemoteAIProvider(config)
        assert provider.get_name() == "remote"

    def test_not_available_without_url(self):
        config = AIProviderConfig()
        provider = RemoteAIProvider(config)
        assert not provider.is_available()

    def test_available_with_url(self):
        config = AIProviderConfig(remote_ai_url="https://ai.example.com")
        provider = RemoteAIProvider(config)
        assert provider.is_available()

    def test_ask_no_url(self):
        config = AIProviderConfig()
        provider = RemoteAIProvider(config)
        result = provider.ask("system prompt", "user message")
        assert not result.success
        assert "REMOTE_AI_URL" in result.error

    def test_ask_success(self):
        config = AIProviderConfig(remote_ai_url="https://ai.example.com", remote_ai_token="tok")
        provider = RemoteAIProvider(config)
        decision = {"actions": [{"type": "buy", "symbol": "ETHUSDT"}]}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"decision": decision, "model": "remote-v1"}
        mock_resp.raise_for_status = MagicMock()
        with patch("app.ai.remote_provider.httpx.post", return_value=mock_resp):
            result = provider.ask("system prompt", "user message")
        assert result.success
        assert result.decision == decision
        assert result.model == "remote-v1"

    def test_ask_http_error(self):
        config = AIProviderConfig(remote_ai_url="https://ai.example.com")
        provider = RemoteAIProvider(config)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        with patch("app.ai.remote_provider.httpx.post", return_value=mock_resp):
            result = provider.ask("system prompt", "user message")
        assert not result.success
        assert result.error is not None
