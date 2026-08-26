"""Tests for audit log service."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAuditLog:
    """Tests for audit log service."""

    def test_log_audit_creates_event(self):
        """Should create an audit log entry."""
        from app.services.audit_log import log_audit

        # Mock the database session
        mock_db = MagicMock()
        mock_event = MagicMock()
        mock_event.id = 1

        with patch("app.services.audit_log.SessionLocal", return_value=mock_db):
            with patch("app.services.audit_log.SystemEvent") as MockEvent:
                MockEvent.return_value = mock_event
                result = log_audit(
                    user_id=1,
                    source="auth",
                    message="User logged in",
                    level="info",
                    details={"ip": "127.0.0.1"},
                )

                assert result is not None
                assert mock_db.add.called
                assert mock_db.commit.called

    def test_log_audit_invalid_level_defaults_to_info(self):
        """Should default to 'info' level for invalid level."""
        from app.services.audit_log import log_audit

        mock_db = MagicMock()

        with patch("app.services.audit_log.SessionLocal", return_value=mock_db):
            with patch("app.services.audit_log.SystemEvent") as MockEvent:
                MockEvent.return_value = MagicMock(id=1)
                log_audit(
                    user_id=1,
                    source="test",
                    message="Test event",
                    level="invalid_level",
                )

                # Check that the level was set to "info"
                call_kwargs = MockEvent.call_args[1]
                assert call_kwargs["level"] == "info"

    def test_log_audit_handles_db_error(self):
        """Should return None when database fails."""
        from app.services.audit_log import log_audit

        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB error")

        with patch("app.services.audit_log.SessionLocal", return_value=mock_db):
            with patch("app.services.audit_log.SystemEvent"):
                result = log_audit(user_id=1, source="test", message="Test")
                assert result is None
                assert mock_db.rollback.called

    def test_log_login_success(self):
        """Should log login success with info level."""
        from app.services.audit_log import log_login

        with patch("app.services.audit_log.log_audit") as mock_log:
            log_login(user_id=1, success=True, ip="127.0.0.1")
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["source"] == "auth"
            assert call_kwargs["level"] == "info"
            assert "succeeded" in call_kwargs["message"]

    def test_log_login_failure(self):
        """Should log login failure with warning level."""
        from app.services.audit_log import log_login

        with patch("app.services.audit_log.log_audit") as mock_log:
            log_login(user_id=1, success=False, ip="127.0.0.1")
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["level"] == "warning"
            assert "failed" in call_kwargs["message"]

    def test_log_broker_connect(self):
        """Should log broker connect event."""
        from app.services.audit_log import log_broker_connect

        with patch("app.services.audit_log.log_audit") as mock_log:
            log_broker_connect(user_id=1, broker_id="binance", success=True)
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["source"] == "broker"
            assert "binance" in call_kwargs["message"]

    def test_log_order_placed(self):
        """Should log order placement with all details."""
        from app.services.audit_log import log_order_placed

        with patch("app.services.audit_log.log_audit") as mock_log:
            log_order_placed(
                user_id=1,
                broker_id="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=0.1,
                order_type="market",
            )
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["source"] == "trading"
            assert "buy" in call_kwargs["message"]
            assert "BTC/USDT" in call_kwargs["message"]
            assert call_kwargs["details"]["symbol"] == "BTC/USDT"

    def test_log_2fa_change(self):
        """Should log 2FA enable/disable."""
        from app.services.audit_log import log_2fa_change

        with patch("app.services.audit_log.log_audit") as mock_log:
            log_2fa_change(user_id=1, enabled=False)
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["source"] == "security"
            assert call_kwargs["level"] == "warning"  # disabling 2FA is warning
            assert "disabled" in call_kwargs["message"]


class TestRateLimit:
    """Tests for rate limiting."""

    def test_sliding_window_allows_under_limit(self):
        """Should allow requests under the limit."""
        from app.middleware.rate_limit import SlidingWindowCounter

        limiter = SlidingWindowCounter()
        for i in range(5):
            allowed, count, retry = limiter.check("test_key", limit=10, window=60)
            assert allowed is True
            assert count == i + 1
            assert retry == 0

    def test_sliding_window_blocks_over_limit(self):
        """Should block requests over the limit."""
        from app.middleware.rate_limit import SlidingWindowCounter

        limiter = SlidingWindowCounter()
        for _ in range(5):
            limiter.check("test_key", limit=5, window=60)

        allowed, count, retry = limiter.check("test_key", limit=5, window=60)
        assert allowed is False
        assert retry > 0

    def test_sliding_window_different_keys_independent(self):
        """Different keys should have independent limits."""
        from app.middleware.rate_limit import SlidingWindowCounter

        limiter = SlidingWindowCounter()
        # Exhaust key1
        for _ in range(5):
            limiter.check("key1", limit=5, window=60)

        # key2 should still be allowed
        allowed, count, _ = limiter.check("key2", limit=5, window=60)
        assert allowed is True
        assert count == 1

    def test_get_rate_limit_for_path(self):
        """Should return correct rate limit for known paths."""
        from app.middleware.rate_limit import get_rate_limit_for_path

        # Auth endpoints have strict limits
        limit, window = get_rate_limit_for_path("/api/auth/login")
        assert limit == 10
        assert window == 60

        # Trading endpoints
        limit, window = get_rate_limit_for_path("/api/trading/order")
        assert limit == 30

        # Unknown paths use default
        limit, window = get_rate_limit_for_path("/api/unknown")
        assert limit == 100

    def test_limiter_stats(self):
        """Should return stats with tracked keys count."""
        from app.middleware.rate_limit import SlidingWindowCounter

        limiter = SlidingWindowCounter()
        limiter.check("key1", limit=10, window=60)
        limiter.check("key2", limit=10, window=60)

        # Access internal stats via the global function
        from app.middleware.rate_limit import get_limiter_stats
        stats = get_limiter_stats()
        assert "configured_limits" in stats
        assert "default_limit" in stats
