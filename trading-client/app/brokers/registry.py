"""Registry de brokers — unico lugar donde se decide el broker por id.

Binance usa BinanceAdapter nativo (HMAC propio, cache exchangeInfo, futures OCO).
Todos los demas exchanges usan CCXTAdapter (100+ exchanges via libreria CCXT).

Detras del flag ENABLE_MULTI_BROKER (por defecto solo Binance).
Fuera de este modulo, ningun condicional por nombre de broker.
"""

from __future__ import annotations

from app.brokers.adapters.ccxt_adapter import (
    CCXTAdapter,
    get_curated_exchange_ids,
    get_exchange_meta,
)
from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.capabilities import BrokerCapabilities
from app.brokers.models import BrokerCredentials, BrokerInfo
from app.config import get_settings

# Binance usa adapter nativo. El resto via CCXT.
_BINANCE_ID = "binance"

# Todos los brokers soportados: Binance nativo + exchanges CCXT curados.
_BROKER_IDS: tuple[str, ...] = (_BINANCE_ID,) + get_curated_exchange_ids()

_ADAPTER_CLASSES: dict[str, type[BrokerAdapter]] = {}


def _register_adapters() -> None:
    """Registra las clases de adaptadores de forma perezosa."""
    if _ADAPTER_CLASSES:
        return
    from app.brokers.adapters.binance_adapter import BinanceAdapter

    _ADAPTER_CLASSES[_BINANCE_ID] = BinanceAdapter

    for exchange_id in get_curated_exchange_ids():
        _ADAPTER_CLASSES[exchange_id] = CCXTAdapter


def list_brokers() -> list[BrokerInfo]:
    """Devuelve informacion de todos los brokers registrados.

    No requiere credenciales — solo metadatos estaticos.
    """
    _register_adapters()
    brokers: list[BrokerInfo] = []
    for _broker_id, cls in _ADAPTER_CLASSES.items():
        if _broker_id == _BINANCE_ID:
            dummy = cls.__new__(cls)
            brokers.append(dummy.get_broker_info())
        else:
            meta = get_exchange_meta(_broker_id)
            brokers.append(
                BrokerInfo(
                    broker_id=_broker_id,
                    display_name=meta.get("display_name", _broker_id.title()),
                    supported_markets=meta.get("markets", ()),
                    website_url=meta.get("website"),
                    api_docs_url=meta.get("api_docs"),
                )
            )
    return brokers


def get_capabilities(broker_id: str) -> BrokerCapabilities:
    """Devuelve las capacidades de un broker sin necesidad de credenciales."""
    _register_adapters()
    broker_id = broker_id.lower().strip()
    cls = _ADAPTER_CLASSES.get(broker_id)
    if cls is None:
        raise BrokerError(f"Broker desconocido: {broker_id}")
    if broker_id == _BINANCE_ID:
        dummy = cls.__new__(cls)
        return dummy.get_capabilities()
    meta = get_exchange_meta(broker_id)
    from app.brokers.models import MarketType

    markets = meta.get("markets", (MarketType.SPOT,))
    return BrokerCapabilities(
        spot=MarketType.SPOT in markets,
        margin=MarketType.MARGIN in markets,
        futures=MarketType.FUTURES in markets,
        staking=False,
        earn=False,
        websocket=False,
        market_orders=True,
        limit_orders=True,
        stop_orders=False,
        withdrawals=False,
    )


def get_adapter(broker_id: str, credentials: BrokerCredentials, market_type: str = "spot") -> BrokerAdapter:
    """Crea y devuelve un adaptador de broker.

    Args:
        broker_id: Identificador del broker (ej: "binance", "bybit", "kraken").
        credentials: Credenciales normalizadas para el broker.
        market_type: "spot", "future", "swap", o "margin" (para CCXT exchanges).

    Returns:
        Instancia de BrokerAdapter lista para usar.

    Raises:
        BrokerError: Si el broker_id no es valido o multi-broker esta deshabilitado.
    """
    _register_adapters()

    broker_id = broker_id.lower().strip()

    settings = get_settings()
    multi_broker_enabled = getattr(settings, "ENABLE_MULTI_BROKER", False)

    if broker_id != _BINANCE_ID and not multi_broker_enabled:
        raise BrokerError(
            f"Multi-broker deshabilitado. Solo 'binance' esta disponible. "
            f"Habilita ENABLE_MULTI_BROKER para usar '{broker_id}'."
        )

    cls = _ADAPTER_CLASSES.get(broker_id)
    if cls is None:
        raise BrokerError(f"Broker desconocido: {broker_id}. Disponibles: {', '.join(_BROKER_IDS)}")

    if broker_id == _BINANCE_ID:
        return cls(credentials)
    # CCXTAdapter requiere exchange_id extra + market_type opcional
    return cls(credentials, exchange_id=broker_id, market_type=market_type)


def get_available_broker_ids() -> tuple[str, ...]:
    """Devuelve los IDs de brokers disponibles segun configuracion."""
    if getattr(get_settings(), "ENABLE_MULTI_BROKER", False):
        return _BROKER_IDS
    return (_BINANCE_ID,)


# Todos los brokers estan implementados: Binance nativo + CCXT para el resto.
_IMPLEMENTED_BROKERS: frozenset[str] = frozenset(_BROKER_IDS)


def is_implemented(broker_id: str) -> bool:
    """Devuelve True si el adapter del broker esta completamente implementado."""
    return broker_id.lower().strip() in _IMPLEMENTED_BROKERS
