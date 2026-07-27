"""Capacidades declaradas por cada broker.

withdrawals esta forzado a False por diseno. No se implementa ni se planea.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerCapabilities:
    """Declara que funcionalidades soporta un broker.

    withdrawals es siempre False. Es un campo que existe solo para
    poder responder a la pregunta 'soporta retiros?' con un False
    explicito y documentado, no con un AttributeError.
    """

    spot: bool = False
    margin: bool = False
    futures: bool = False
    staking: bool = False
    earn: bool = False
    websocket: bool = False
    market_orders: bool = False
    limit_orders: bool = False
    stop_orders: bool = False
    withdrawals: bool = False  # Siempre False. No modificar.

    def supports(self, capability: str) -> bool:
        """Verifica si el broker soporta una capacidad por nombre."""
        return bool(getattr(self, capability, False))
