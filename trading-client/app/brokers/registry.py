"""Registry de brokers — unico lugar donde se decide el broker por id.

Detras del flag ENABLE_MULTI_BROKER (por defecto solo Binance).
Fuera de este modulo, ningun condicional por nombre de broker.
"""

from __future__ import annotations

from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import BrokerCredentials, BrokerInfo
from app.config import get_settings

_BROKER_IDS: tuple[str, ...] = ("binance", "bybit", "coinbase", "kraken", "okx")

_ADAPTER_CLASSES: dict[str, type[BrokerAdapter]] = {}


def _register_adapters() -> None:
    """Registra las clases de adaptadores de forma perezosa."""
    if _ADAPTER_CLASSES:
        return
    from app.brokers.adapters.binance_adapter import BinanceAdapter
    from app.brokers.adapters.bybit_adapter import BybitAdapter
    from app.brokers.adapters.coinbase_adapter import CoinbaseAdapter
    from app.brokers.adapters.kraken_adapter import KrakenAdapter
    from app.brokers.adapters.okx_adapter import OKXAdapter

    _ADAPTER_CLASSES.update(
        {
            "binance": BinanceAdapter,
            "bybit": BybitAdapter,
            "coinbase": CoinbaseAdapter,
            "kraken": KrakenAdapter,
            "okx": OKXAdapter,
        }
    )


def list_brokers() -> list[BrokerInfo]:
    """Devuelve informacion de todos los brokers registrados.

    No requiere credenciales — solo metadatos estaticos.
    """
    _register_adapters()
    brokers: list[BrokerInfo] = []
    for _broker_id, cls in _ADAPTER_CLASSES.items():
        dummy = cls.__new__(cls)
        brokers.append(dummy.get_broker_info())
    return brokers


def get_capabilities(broker_id: str) -> BrokerCapabilities:
    """Devuelve las capacidades de un broker sin necesidad de credenciales."""
    _register_adapters()
    broker_id = broker_id.lower().strip()
    cls = _ADAPTER_CLASSES.get(broker_id)
    if cls is None:
        raise BrokerError(f"Broker desconocido: {broker_id}")
    dummy = cls.__new__(cls)
    return dummy.get_capabilities()


def get_adapter(broker_id: str, credentials: BrokerCredentials) -> BrokerAdapter:
    """Crea y devuelve un adaptador de broker.

    Args:
        broker_id: Identificador del broker (ej: "binance").
        credentials: Credenciales normalizadas para el broker.

    Returns:
        Instancia de BrokerAdapter lista para usar.

    Raises:
        BrokerError: Si el broker_id no es valido o multi-broker esta deshabilitado.
    """
    _register_adapters()

    broker_id = broker_id.lower().strip()

    settings = get_settings()
    multi_broker_enabled = getattr(settings, "ENABLE_MULTI_BROKER", False)

    if broker_id != "binance" and not multi_broker_enabled:
        raise BrokerError(
            f"Multi-broker deshabilitado. Solo 'binance' esta disponible. "
            f"Habilita ENABLE_MULTI_BROKER para usar '{broker_id}'."
        )

    cls = _ADAPTER_CLASSES.get(broker_id)
    if cls is None:
        raise BrokerError(f"Broker desconocido: {broker_id}. Disponibles: {', '.join(_BROKER_IDS)}")

    return cls(credentials)


def get_available_broker_ids() -> tuple[str, ...]:
    """Devuelve los IDs de brokers disponibles segun configuracion."""
    if getattr(get_settings(), "ENABLE_MULTI_BROKER", False):
        return _BROKER_IDS
    return ("binance",)
