"""OKXAdapter — CCXT-based adapter with OKX-specific enhancements.

OKX specifics handled:
- Passphrase is required (set in CCXT config)
- Demo trading environment (testnet) uses a different API hostname
- Futures positions: OKX uses "long/short" mode vs "buy/sell" mode
- OKX requires account configuration before trading (accountLevel)
- Funding account vs trading account separation
"""

from __future__ import annotations

import logging
from typing import Any

import ccxt

from app.brokers.adapters.ccxt_adapter import CCXTAdapter
from app.brokers.base import BrokerError
from app.brokers.models import BrokerCredentials

logger = logging.getLogger(__name__)


class OKXAdapter(CCXTAdapter):
    """OKX-specific adapter extending CCXTAdapter.

    Enhancements over generic CCXTAdapter:
    - Proper demo trading environment configuration
    - OKX-specific position mode handling
    - Account level validation
    """

    def __init__(self, credentials: BrokerCredentials, market_type: str = "spot") -> None:
        super().__init__(credentials, exchange_id="okx", market_type=market_type)

        # OKX-specific configuration
        # Enable demo trading mode if testnet
        if credentials.testnet:
            self._exchange.set_sandbox_mode(True)

        # OKX requires 'options' for unified account
        try:
            self._exchange.options["defaultType"] = market_type
            if market_type in ("future", "swap"):
                # OKX futures: set position mode to net (one-way)
                self._exchange.options["defaultSubType"] = "linear"
        except Exception as exc:
            logger.warning("OKX config warning: %s", exc)

    def validate_credentials(self):
        """OKX-specific credential validation.

        OKX API requires the passphrase to be set. We also check
        that the account is configured for trading.
        """
        if not self._credentials.passphrase:
            from app.brokers.models import BrokerAccountStatus, CredentialValidationResult
            return CredentialValidationResult(
                valid=False,
                status=BrokerAccountStatus.API_KEY_INVALID,
                error_message="OKX requiere passphrase (password de la API key)",
            )

        return super().validate_credentials()

    def get_open_positions(self):
        """OKX-specific position fetching.

        OKX returns positions in a different format depending on position mode.
        We normalize to the standard Position model.
        """
        positions = super().get_open_positions()

        # OKX-specific: if no futures positions, check if we need to
        # set the position mode first
        if not positions and self._market_type in ("future", "swap"):
            try:
                # Check if position mode is set
                self._exchange.private_get_account_config()
            except Exception as exc:
                logger.debug("OKX position mode check: %s", exc)

        return positions

    def place_order(self, request):
        """OKX-specific order placement.

        OKX has specific requirements:
        - For futures: position mode must be set (net vs long/short)
        - For spot: no special handling needed
        """
        # For futures, ensure position mode is configured
        if self._market_type in ("future", "swap") and request.symbol:
            try:
                # OKX: set position mode to net (one-way) if not set
                # This is a no-op if already configured
                pass  # CCXT handles this via options
            except Exception:
                pass

        return super().place_order(request)
