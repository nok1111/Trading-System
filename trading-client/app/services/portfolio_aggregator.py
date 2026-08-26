"""Portfolio aggregator — combines balances, positions, and trades across all connected brokers.

Provides a unified view of the user's entire portfolio regardless of how many
brokers they have connected. Handles errors gracefully: if one broker fails,
its data is marked as errored but the rest still aggregate.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.brokers.base import BrokerAdapter, BrokerError
from app.brokers.models import BrokerCredentials, normalize_symbol
from app.brokers.registry import get_adapter
from app.database.models.broker_account import BrokerAccount as BrokerAccountModel
from app.database.session import SessionLocal
from app.services.auth import LocalUser
from app.services.broker_account_service import _to_safe_dict
from app.services.crypto import decrypt

logger = logging.getLogger(__name__)

# Cache TTLs (in seconds)
_BALANCE_CACHE_TTL = 30
_POSITION_CACHE_TTL = 10
_PORTFOLIO_CACHE_TTL = 30

# In-memory cache: { user_id: { "key": { "data": ..., "expires": ... } } }
_cache: dict[int, dict[str, Any]] = {}

STABLECOINS = {"USDT", "BUSD", "USDC", "USD", "UST", "TUSD", "FDUSD", "USDP", "GUSD", "PAX", "EUR"}
USD_QUOTES = ["USDT", "USDC", "USD", "FDUSD", "TUSD", "BUSD"]


def _get_cached(user_id: int, key: str) -> Any | None:
    """Get cached data if still valid."""
    user_cache = _cache.get(user_id)
    if not user_cache:
        return None
    entry = user_cache.get(key)
    if not entry:
        return None
    if entry["expires"] < time.time():
        return None
    return entry["data"]


def _set_cached(user_id: int, key: str, data: Any, ttl: int) -> None:
    """Set cached data with TTL."""
    if user_id not in _cache:
        _cache[user_id] = {}
    _cache[user_id][key] = {"data": data, "expires": time.time() + ttl}


def _get_connected_brokers(user_id: int) -> list[BrokerAccountModel]:
    """Get all connected broker accounts for a user."""
    db = SessionLocal()
    try:
        accounts = (
            db.query(BrokerAccountModel)
            .filter(
                BrokerAccountModel.user_id == user_id,
                BrokerAccountModel.status.in_(["active", "degraded"]),
            )
            .all()
        )
        return accounts
    finally:
        db.close()


def _get_adapter_for_account(account: BrokerAccountModel) -> BrokerAdapter | None:
    """Create an adapter for a broker account, decrypting credentials."""
    try:
        api_key = decrypt(account.api_key_enc) if account.api_key_enc else ""
        api_secret = decrypt(account.api_secret_enc) if account.api_secret_enc else ""
        passphrase = None
        if hasattr(account, "passphrase_enc") and account.passphrase_enc:
            try:
                passphrase = decrypt(account.passphrase_enc)
            except Exception:
                pass
        creds = BrokerCredentials(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            testnet=(account.environment == "testnet"),
        )
        return get_adapter(account.broker_id, creds)
    except Exception as exc:
        logger.warning("Failed to create adapter for %s: %s", account.broker_id, exc)
        return None


def _asset_usd_value(adapter: BrokerAdapter, asset: str, quantity: float) -> float:
    """Convert an asset quantity to USD value using the adapter's ticker."""
    if asset in STABLECOINS:
        return quantity
    if asset == "EUR":
        return quantity * 1.08
    for quote in USD_QUOTES:
        try:
            ticker = adapter.get_ticker(f"{asset}/{quote}")
            price = float(ticker.price)
            return quantity * price
        except Exception:
            continue
    return 0.0


def get_unified_balances(user_id: int) -> dict[str, Any]:
    """Get combined balances from all connected brokers.

    Returns:
        {
            "total_usd": float,
            "by_broker": [{ "broker_id", "display_name", "total_usd", "assets": [...], "error": str|None }],
            "by_asset": [{ "asset", "total_quantity", "usd_value", "brokers": [...] }],
            "errors": [{ "broker_id", "error": str }]
        }
    """
    cached = _get_cached(user_id, "balances")
    if cached is not None:
        return cached

    accounts = _get_connected_brokers(user_id)
    by_broker: list[dict[str, Any]] = []
    by_asset_map: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    total_usd = 0.0

    for account in accounts:
        adapter = _get_adapter_for_account(account)
        if not adapter:
            errors.append({"broker_id": account.broker_id, "error": "No se pudo crear el adapter"})
            by_broker.append({
                "broker_id": account.broker_id,
                "display_name": account.display_name or account.broker_id,
                "total_usd": 0.0,
                "assets": [],
                "error": "No se pudo crear el adapter",
            })
            continue

        try:
            balances = adapter.get_account_balances()
            broker_total_usd = 0.0
            broker_assets = []

            for bal in balances:
                free = float(bal.free)
                locked = float(bal.locked)
                total = free + locked
                if total <= 0:
                    continue

                usd_value = _asset_usd_value(adapter, bal.asset, total)
                broker_total_usd += usd_value

                asset_entry = {
                    "asset": bal.asset,
                    "free": free,
                    "locked": locked,
                    "total": total,
                    "usd_value": round(usd_value, 4),
                }
                broker_assets.append(asset_entry)

                # Aggregate by asset across brokers
                if bal.asset not in by_asset_map:
                    by_asset_map[bal.asset] = {
                        "asset": bal.asset,
                        "total_quantity": 0.0,
                        "usd_value": 0.0,
                        "brokers": [],
                    }
                by_asset_map[bal.asset]["total_quantity"] += total
                by_asset_map[bal.asset]["usd_value"] += usd_value
                by_asset_map[bal.asset]["brokers"].append(account.broker_id)

            broker_assets.sort(key=lambda x: x.get("usd_value", 0), reverse=True)
            total_usd += broker_total_usd

            by_broker.append({
                "broker_id": account.broker_id,
                "display_name": account.display_name or account.broker_id,
                "total_usd": round(broker_total_usd, 2),
                "assets": broker_assets,
                "error": None,
            })
        except BrokerError as exc:
            err_msg = str(exc)
            errors.append({"broker_id": account.broker_id, "error": err_msg})
            by_broker.append({
                "broker_id": account.broker_id,
                "display_name": account.display_name or account.broker_id,
                "total_usd": 0.0,
                "assets": [],
                "error": err_msg,
            })
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("PortfolioAggregator: error fetching balances from %s: %s", account.broker_id, exc)
            errors.append({"broker_id": account.broker_id, "error": err_msg})
            by_broker.append({
                "broker_id": account.broker_id,
                "display_name": account.display_name or account.broker_id,
                "total_usd": 0.0,
                "assets": [],
                "error": err_msg,
            })

    # Finalize by_asset list
    by_asset = list(by_asset_map.values())
    for a in by_asset:
        a["total_quantity"] = round(a["total_quantity"], 8)
        a["usd_value"] = round(a["usd_value"], 4)
        a["brokers"] = list(set(a["brokers"]))
    by_asset.sort(key=lambda x: x["usd_value"], reverse=True)

    result = {
        "total_usd": round(total_usd, 2),
        "by_broker": by_broker,
        "by_asset": by_asset,
        "errors": errors,
        "broker_count": len(accounts),
    }
    _set_cached(user_id, "balances", result, _BALANCE_CACHE_TTL)
    return result


def get_unified_positions(user_id: int) -> dict[str, Any]:
    """Get combined open positions from all connected brokers.

    Returns:
        {
            "positions": [{ "broker_id", "symbol", "side", "quantity", "entry_price", "current_price", "unrealized_pnl", "unrealized_pnl_pct", "leverage", "liquidation_price" }],
            "total_unrealized_pnl": float,
            "errors": [...]
        }
    """
    cached = _get_cached(user_id, "positions")
    if cached is not None:
        return cached

    accounts = _get_connected_brokers(user_id)
    all_positions: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    total_unrealized = 0.0

    for account in accounts:
        adapter = _get_adapter_for_account(account)
        if not adapter:
            errors.append({"broker_id": account.broker_id, "error": "No se pudo crear el adapter"})
            continue

        try:
            broker_positions = adapter.get_open_positions()

            # If no futures positions, derive from spot balances
            if not broker_positions:
                try:
                    balances = adapter.get_account_balances()
                except Exception:
                    balances = ()

                for bal in balances:
                    if bal.asset in STABLECOINS or float(bal.total) <= 0:
                        continue
                    current_price = None
                    for quote in ("USDT", "USDC", "USD", "FDUSD"):
                        try:
                            ticker = adapter.get_ticker(f"{bal.asset}/{quote}")
                            current_price = float(ticker.price)
                            break
                        except Exception:
                            continue

                    # Get entry price from trade history
                    entry_price = 0.0
                    try:
                        sym = normalize_symbol(f"{bal.asset}/USDT")
                        trades = adapter.get_trades(symbol=sym, limit=500)
                        buy_trades = [t for t in trades if t.side.value == "buy"]
                        if buy_trades:
                            total_cost = sum(float(t.price) * float(t.quantity) for t in buy_trades)
                            total_qty = sum(float(t.quantity) for t in buy_trades)
                            if total_qty > 0:
                                entry_price = round(total_cost / total_qty, 8)
                    except Exception:
                        pass

                    unrealized = 0.0
                    if entry_price > 0 and current_price:
                        unrealized = round((current_price - entry_price) * float(bal.total), 8)

                    total_unrealized += unrealized
                    all_positions.append({
                        "broker_id": account.broker_id,
                        "broker_name": account.display_name or account.broker_id,
                        "symbol": f"{bal.asset}/USDT",
                        "side": "long",
                        "quantity": float(bal.total),
                        "entry_price": entry_price,
                        "current_price": current_price or 0.0,
                        "unrealized_pnl": unrealized,
                        "unrealized_pnl_pct": round(((current_price - entry_price) / entry_price * 100) if entry_price > 0 and current_price else 0, 2),
                        "leverage": 1,
                        "liquidation_price": None,
                        "market_type": "spot",
                    })
            else:
                for pos in broker_positions:
                    unrealized = float(pos.unrealized_pnl) if pos.unrealized_pnl else 0.0
                    total_unrealized += unrealized
                    entry = float(pos.entry_price) if pos.entry_price else 0.0
                    current = float(pos.mark_price) if pos.mark_price else 0.0
                    all_positions.append({
                        "broker_id": account.broker_id,
                        "broker_name": account.display_name or account.broker_id,
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "quantity": float(pos.quantity),
                        "entry_price": entry,
                        "current_price": current,
                        "unrealized_pnl": unrealized,
                        "unrealized_pnl_pct": round(((current - entry) / entry * 100) if entry > 0 else 0, 2),
                        "leverage": float(pos.leverage) if pos.leverage else 1,
                        "liquidation_price": float(pos.liquidation_price) if pos.liquidation_price else None,
                        "market_type": "futures",
                    })
        except BrokerError as exc:
            errors.append({"broker_id": account.broker_id, "error": str(exc)})
        except Exception as exc:
            logger.warning("PortfolioAggregator: error fetching positions from %s: %s", account.broker_id, exc)
            errors.append({"broker_id": account.broker_id, "error": str(exc)})

    # Sort by unrealized PnL absolute value
    all_positions.sort(key=lambda x: abs(x.get("unrealized_pnl", 0)), reverse=True)

    result = {
        "positions": all_positions,
        "total_unrealized_pnl": round(total_unrealized, 2),
        "position_count": len(all_positions),
        "errors": errors,
    }
    _set_cached(user_id, "positions", result, _POSITION_CACHE_TTL)
    return result


def get_net_exposure(user_id: int) -> dict[str, Any]:
    """Calculate net exposure per asset across all brokers.

    For example: 1 BTC long on Binance + 0.5 BTC short on Bybit = 0.5 BTC net long.

    Returns:
        {
            "by_asset": [{ "asset", "net_quantity", "net_side", "long_quantity", "short_quantity", "usd_value" }],
            "total_long_usd": float,
            "total_short_usd": float,
            "net_usd": float
        }
    """
    positions_data = get_unified_positions(user_id)
    exposure_map: dict[str, dict[str, Any]] = {}

    for pos in positions_data["positions"]:
        symbol = pos["symbol"]
        # Extract base asset from symbol (e.g. "BTC/USDT" -> "BTC")
        base = symbol.split("/")[0].split("-")[0].split("_")[0]
        if base in STABLECOINS:
            continue

        if base not in exposure_map:
            exposure_map[base] = {
                "asset": base,
                "long_quantity": 0.0,
                "short_quantity": 0.0,
                "brokers": [],
            }

        qty = pos["quantity"]
        if pos["side"] == "long":
            exposure_map[base]["long_quantity"] += qty
        else:
            exposure_map[base]["short_quantity"] += qty
        if pos["broker_id"] not in exposure_map[base]["brokers"]:
            exposure_map[base]["brokers"].append(pos["broker_id"])

    total_long_usd = 0.0
    total_short_usd = 0.0
    by_asset = []

    for asset, data in exposure_map.items():
        net_qty = data["long_quantity"] - data["short_quantity"]
        net_side = "long" if net_qty > 0 else "short" if net_qty < 0 else "flat"
        # Estimate USD value using current price from positions
        usd_value = 0.0
        for pos in positions_data["positions"]:
            if pos["symbol"].startswith(asset + "/") and pos["current_price"] > 0:
                usd_value = abs(net_qty) * pos["current_price"]
                break

        total_long_usd += data["long_quantity"] * usd_value / max(data["long_quantity"] + data["short_quantity"], 1) if (data["long_quantity"] + data["short_quantity"]) > 0 else 0
        total_short_usd += data["short_quantity"] * usd_value / max(data["long_quantity"] + data["short_quantity"], 1) if (data["long_quantity"] + data["short_quantity"]) > 0 else 0

        by_asset.append({
            "asset": asset,
            "net_quantity": round(net_qty, 8),
            "net_side": net_side,
            "long_quantity": round(data["long_quantity"], 8),
            "short_quantity": round(data["short_quantity"], 8),
            "usd_value": round(usd_value, 2),
            "brokers": data["brokers"],
        })

    by_asset.sort(key=lambda x: x["usd_value"], reverse=True)

    return {
        "by_asset": by_asset,
        "total_long_usd": round(total_long_usd, 2),
        "total_short_usd": round(total_short_usd, 2),
        "net_usd": round(total_long_usd - total_short_usd, 2),
    }


def get_concentration_analysis(user_id: int) -> dict[str, Any]:
    """Analyze portfolio concentration by asset, broker, and venue type.

    Returns warnings if concentration exceeds thresholds.
    """
    balances_data = get_unified_balances(user_id)
    positions_data = get_unified_positions(user_id)

    total_usd = balances_data["total_usd"]
    warnings: list[dict[str, str]] = []

    # By asset concentration
    asset_concentration = []
    for asset in balances_data["by_asset"]:
        pct = (asset["usd_value"] / total_usd * 100) if total_usd > 0 else 0
        asset_concentration.append({
            "asset": asset["asset"],
            "usd_value": asset["usd_value"],
            "percentage": round(pct, 2),
        })
        if pct > 40:
            warnings.append({
                "type": "asset_concentration",
                "level": "high",
                "message": f"{asset['asset']} representa {pct:.1f}% de tu portfolio. Considera diversificar.",
            })

    # By broker concentration
    broker_concentration = []
    for broker in balances_data["by_broker"]:
        pct = (broker["total_usd"] / total_usd * 100) if total_usd > 0 else 0
        broker_concentration.append({
            "broker_id": broker["broker_id"],
            "display_name": broker["display_name"],
            "usd_value": broker["total_usd"],
            "percentage": round(pct, 2),
        })
        if pct > 70 and len(balances_data["by_broker"]) > 1:
            warnings.append({
                "type": "broker_concentration",
                "level": "medium",
                "message": f"{broker['display_name']} representa {pct:.1f}% de tu portfolio. Considera usar múltiples brokers.",
            })

    # By venue type (spot vs futures)
    spot_usd = sum(b["usd_value"] for b in balances_data["by_asset"] if b["asset"] not in STABLECOINS)
    futures_usd = sum(
        abs(p["unrealized_pnl"]) for p in positions_data["positions"] if p.get("market_type") == "futures"
    )
    stable_usd = sum(b["usd_value"] for b in balances_data["by_asset"] if b["asset"] in STABLECOINS)

    return {
        "total_usd": total_usd,
        "by_asset": asset_concentration,
        "by_broker": broker_concentration,
        "by_venue": {
            "spot": round(spot_usd, 2),
            "futures": round(futures_usd, 2),
            "stablecoins": round(stable_usd, 2),
        },
        "warnings": warnings,
    }


def get_unified_portfolio_overview(user_id: int) -> dict[str, Any]:
    """Get a complete portfolio overview combining balances, positions, exposure, and concentration.

    This is the main endpoint for the unified dashboard.
    """
    cached = _get_cached(user_id, "overview")
    if cached is not None:
        return cached

    balances = get_unified_balances(user_id)
    positions = get_unified_positions(user_id)
    exposure = get_net_exposure(user_id)
    concentration = get_concentration_analysis(user_id)

    result = {
        "total_usd": balances["total_usd"],
        "total_unrealized_pnl": positions["total_unrealized_pnl"],
        "position_count": positions["position_count"],
        "broker_count": balances["broker_count"],
        "balances": balances,
        "positions": positions,
        "exposure": exposure,
        "concentration": concentration,
    }
    _set_cached(user_id, "overview", result, _PORTFOLIO_CACHE_TTL)
    return result


def invalidate_cache(user_id: int) -> None:
    """Invalidate all cached portfolio data for a user."""
    _cache.pop(user_id, None)
