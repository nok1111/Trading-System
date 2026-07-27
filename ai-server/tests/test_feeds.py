"""Tests for data feeds — real API implementations with graceful degradation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.feeds import (
    MacroData,
    MacroFeed,
    NewsFeed,
    NewsItem,
    OnchainData,
    OnchainFeed,
    SentimentData,
    SentimentFeed,
)


class TestNewsFeed:
    def test_disabled_returns_empty(self):
        feed = NewsFeed()
        with patch("app.services.feeds.settings") as mock_settings:
            mock_settings.ENABLE_NEWS_FEED = False
            result = feed.fetch()
        assert result == []

    def test_enabled_no_token_returns_empty(self):
        feed = NewsFeed()
        with patch("app.services.feeds.settings") as mock_settings:
            mock_settings.ENABLE_NEWS_FEED = True
            mock_settings.NEWS_API_TOKEN = None
            result = feed.fetch()
        assert result == []

    def test_fetch_success(self):
        feed = NewsFeed()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "BTC hits new high",
                    "source": {"name": "CoinDesk"},
                    "url": "https://example.com/news/1",
                    "published_at": "2024-01-01T00:00:00Z",
                    "currencies": [{"code": "BTC"}],
                    "kind": "news",
                },
            ]
        }
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_NEWS_FEED = True
            mock_settings.NEWS_API_TOKEN = "test-token"
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch(assets=["BTCUSDT"])
        assert len(result) == 1
        assert isinstance(result[0], NewsItem)
        assert result[0].headline == "BTC hits new high"
        assert result[0].source == "CoinDesk"
        assert result[0].assets == ["BTC"]

    def test_fetch_http_error_returns_empty(self):
        feed = NewsFeed()
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_NEWS_FEED = True
            mock_settings.NEWS_API_TOKEN = "test-token"
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch()
        assert result == []


class TestOnchainFeed:
    def test_disabled_returns_empty_data(self):
        feed = OnchainFeed()
        with patch("app.services.feeds.settings") as mock_settings:
            mock_settings.ENABLE_ONCHAIN_FEED = False
            result = feed.fetch("BTC")
        assert isinstance(result, OnchainData)
        assert result.asset == "BTC"
        assert result.mvrv is None

    def test_enabled_no_key_returns_empty_data(self):
        feed = OnchainFeed()
        with patch("app.services.feeds.settings") as mock_settings:
            mock_settings.ENABLE_ONCHAIN_FEED = True
            mock_settings.ONCHAIN_API_KEY = None
            result = feed.fetch("BTC")
        assert result.mvrv is None

    def test_fetch_success(self):
        feed = OnchainFeed()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"v": 1.85}]
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_ONCHAIN_FEED = True
            mock_settings.ONCHAIN_API_KEY = "test-key"
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch("BTCUSDT")
        assert result.asset == "BTCUSDT"
        assert result.mvrv == 1.85


class TestMacroFeed:
    def test_disabled_returns_empty_data(self):
        feed = MacroFeed()
        with patch("app.services.feeds.settings") as mock_settings:
            mock_settings.ENABLE_MACRO_FEED = False
            result = feed.fetch()
        assert isinstance(result, MacroData)
        assert result.macro_regime == "unknown"

    def test_fetch_success(self):
        feed = MacroFeed()
        mock_coingecko = MagicMock()
        mock_coingecko.status_code = 200
        mock_coingecko.json.return_value = {
            "data": {"market_cap_percentage": {"btc": 52.3}}
        }
        mock_fng = MagicMock()
        mock_fng.status_code = 200
        mock_fng.json.return_value = {
            "data": [{"value": "75", "value_classification": "Greed"}]
        }
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", side_effect=[mock_coingecko, mock_fng]):
            mock_settings.ENABLE_MACRO_FEED = True
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch()
        assert result.bitcoin_dominance == 52.3
        assert result.macro_regime == "risk_on"

    def test_fetch_fear_returns_risk_off(self):
        feed = MacroFeed()
        mock_coingecko = MagicMock()
        mock_coingecko.status_code = 200
        mock_coingecko.json.return_value = {"data": {}}
        mock_fng = MagicMock()
        mock_fng.status_code = 200
        mock_fng.json.return_value = {
            "data": [{"value": "20", "value_classification": "Fear"}]
        }
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", side_effect=[mock_coingecko, mock_fng]):
            mock_settings.ENABLE_MACRO_FEED = True
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch()
        assert result.macro_regime == "risk_off"


class TestSentimentFeed:
    def test_disabled_returns_empty_data(self):
        feed = SentimentFeed()
        with patch("app.services.feeds.settings") as mock_settings:
            mock_settings.ENABLE_SENTIMENT_FEED = False
            result = feed.fetch("BTC")
        assert isinstance(result, SentimentData)
        assert result.asset == "BTC"
        assert result.fear_greed_index is None

    def test_fetch_success(self):
        feed = SentimentFeed()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"value": "72", "value_classification": "Greed"}]
        }
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_SENTIMENT_FEED = True
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch("BTC")
        assert result.fear_greed_index == 72
        assert result.sentiment_score == pytest.approx(0.44, rel=0.01)
        assert result.narrative == "Greed"
        assert not result.euphoria_detected
        assert not result.fear_detected

    def test_fetch_extreme_greed_detected(self):
        feed = SentimentFeed()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"value": "90", "value_classification": "Extreme Greed"}]
        }
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_SENTIMENT_FEED = True
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch("BTC")
        assert result.euphoria_detected is True
        assert "Extreme Greed" in result.narrative

    def test_fetch_extreme_fear_detected(self):
        feed = SentimentFeed()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"value": "10", "value_classification": "Extreme Fear"}]
        }
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_SENTIMENT_FEED = True
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch("BTC")
        assert result.fear_detected is True
        assert "Extreme Fear" in result.narrative

    def test_fetch_http_error_returns_default(self):
        feed = SentimentFeed()
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("app.services.feeds.settings") as mock_settings, \
             patch("httpx.get", return_value=mock_response):
            mock_settings.ENABLE_SENTIMENT_FEED = True
            mock_settings.FEED_TIMEOUT_SECONDS = 10
            result = feed.fetch("BTC")
        assert result.fear_greed_index is None
        assert result.sentiment_score == 0.0
