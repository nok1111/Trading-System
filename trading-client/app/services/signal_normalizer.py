"""Signal normalizer for cross-broker copy trading.

Normalizes symbols and calculates position sizes when copying signals
between different brokers (e.g. Binance → Bybit, Kraken, Coinbase).
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Mapping of symbol formats between brokers.
# Most brokers use BTCUSDT, but some have exceptions.
_SYMBOL_OVERRIDES: dict[str, dict[str, str]] = {
    "BTCUSDT": {
        "kraken": "XBTUSDT",
        "coinbase": "BTC-USDT",
    },
    "BTCUSD": {
        "kraken": "XBTUSD",
        "coinbase": "BTC-USD",
    },
    "ETHUSDT": {
        "coinbase": "ETH-USDT",
    },
    "SOLUSDT": {
        "coinbase": "SOL-USDT",
    },
}


def normalize_symbol(symbol: str, target_broker: str) -> str:
    """Convert a symbol to the format expected by the target broker.

    Args:
        symbol: Symbol in canonical format (e.g. "BTCUSDT")
        target_broker: Broker ID (e.g. "binance", "kraken", "coinbase")

    Returns:
        Symbol in the target broker's format.
    """
    canonical = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    broker_id = target_broker.lower().strip()

    overrides = _SYMBOL_OVERRIDES.get(canonical, {})
    mapped = overrides.get(broker_id)
    if mapped:
        return mapped

    # Coinbase Pro uses BTC-USDT format
    if broker_id == "coinbase" and canonical.endswith("USDT"):
        base = canonical[:-4]
        return f"{base}-USDT"

    # Default: most brokers use BTCUSDT format
    return canonical


def calculate_copy_size(
    leader_size_pct: float,
    leader_portfolio_usd: float,
    follower_portfolio_usd: float,
    copy_pct: float = 100.0,
) -> Decimal:
    """Calculate the equivalent position size for a follower.

    The idea: if the leader allocates 5% of their $10k portfolio,
    the follower should also allocate 5% of their allocated capital.

    Args:
        leader_size_pct: % of leader's portfolio (e.g. 5.0 = 5%)
        leader_portfolio_usd: Leader's total portfolio value in USD
        follower_portfolio_usd: Follower's total portfolio value in USD
        copy_pct: % of follower's capital allocated to this leader (0-100)

    Returns:
        Position size in USD for the follower.
    """
    if follower_portfolio_usd <= 0 or leader_portfolio_usd <= 0:
        return Decimal("0")

    # Follower's allocated capital = their portfolio * copy_pct
    allocated = follower_portfolio_usd * (copy_pct / 100.0)

    # Position size = same % of allocated capital
    size_usd = allocated * (leader_size_pct / 100.0)

    return Decimal(str(round(size_usd, 2)))


def calculate_quantity(size_usd: Decimal, current_price: Decimal) -> Decimal:
    """Calculate the quantity to buy given a USD size and current price.

    Args:
        size_usd: Position size in USD
        current_price: Current price of the asset

    Returns:
        Quantity to buy/sell.
    """
    if current_price <= 0:
        return Decimal("0")
    qty = size_usd / current_price
    # Round to 6 decimal places (most brokers accept this)
    return qty.quantize(Decimal("0.000001"))


def check_slippage(
    signal_entry_price: Decimal | None,
    current_price: Decimal,
    max_slippage_pct: float = 2.0,
) -> bool:
    """Check if the current price is within acceptable slippage from the signal.

    Args:
        signal_entry_price: Price when the signal was published
        current_price: Current market price
        max_slippage_pct: Maximum allowed slippage (default 2%)

    Returns:
        True if slippage is acceptable, False if too much slippage.
    """
    if signal_entry_price is None or signal_entry_price <= 0:
        return True  # No reference price, allow

    slippage = abs(float(current_price - signal_entry_price) / float(signal_entry_price)) * 100
    return slippage <= max_slippage_pct
