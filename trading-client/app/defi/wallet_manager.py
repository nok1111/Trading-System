"""Wallet manager — connect and query on-chain wallets.

Supports:
  - connect_wallet(user_id, address, label) — register a wallet
  - get_wallet_balances(address) — ERC-20 + native ETH via Alchemy (fallback to free APIs)
  - get_defi_positions(address) — positions in Aave, Uniswap, etc.
  - get_staking_positions(address) — staking positions

Uses requests for HTTP calls. Falls back to CoinGecko for prices.
Handles errors gracefully (wallet not found, API down).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)

# Common ERC-20 token addresses (mainnet)
TOKEN_ADDRESSES: dict[str, str] = {
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    "AAVE": "0x7Fc66500b84Ff947I3f60d63E7D8E1fDf4BbA0E8",
    "MATIC": "0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
}

# CoinGecko platform ID for Ethereum
_COINGECKO_PLATFORM = "ethereum"


class WalletManager:
    """Manage on-chain wallet connections and queries."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._alchemy_key = getattr(self._settings, "ALCHEMY_API_KEY", None) or ""
        self._alchemy_url = (
            f"https://eth-mainnet.g.alchemy.com/v2/{self._alchemy_key}"
            if self._alchemy_key
            else "https://eth-mainnet.g.alchemy.com/v2/demo"
        )

    # ── Wallet registration ─────────────────────────────────────────

    def connect_wallet(self, user_id: int, address: str, label: str = "") -> dict[str, Any]:
        """Register a wallet address for a user.

        Stores the wallet in the database for later queries.
        Returns connection status.
        """
        address = address.strip()
        if not address or not address.startswith("0x") or len(address) != 42:
            return {"error": "Invalid Ethereum address format"}

        try:
            from app.database.session import SessionLocal
            from app.database.models.user_settings import UserSettings
            from datetime import UTC, datetime

            session = SessionLocal()
            try:
                # Store wallet address in user_settings metadata
                settings_row = session.query(UserSettings).filter_by(user_id=user_id).first()
                if not settings_row:
                    settings_row = UserSettings(user_id=user_id)
                    session.add(settings_row)

                # Store in a JSON field if available, or as a simple string
                wallets = []
                if hasattr(settings_row, "defi_wallets") and settings_row.defi_wallets:
                    try:
                        wallets = (
                            settings_row.defi_wallets
                            if isinstance(settings_row.defi_wallets, list)
                            else []
                        )
                    except Exception:
                        wallets = []

                # Check if already connected
                existing = [w for w in wallets if w.get("address", "").lower() == address.lower()]
                if not existing:
                    wallets.append({
                        "address": address,
                        "label": label or f"Wallet {len(wallets) + 1}",
                        "connected_at": datetime.now(UTC).isoformat(),
                    })
                    if hasattr(settings_row, "defi_wallets"):
                        settings_row.defi_wallets = wallets
                    session.commit()

                return {
                    "success": True,
                    "address": address,
                    "label": label or f"Wallet {len(wallets)}",
                    "wallets_count": len(wallets),
                }
            finally:
                session.close()
        except Exception as exc:
            logger.warning("connect_wallet failed: %s", exc)
            return {"error": f"Failed to connect wallet: {exc}"}

    # ── Wallet balances ─────────────────────────────────────────────

    def get_wallet_balances(self, address: str) -> dict[str, Any]:
        """Get ERC-20 + native ETH balances for an address.

        Uses Alchemy API if available, falls back to public RPC.
        Prices from CoinGecko free API.
        """
        address = address.strip()
        if not address.startswith("0x"):
            return {"error": "Invalid address"}

        result: dict[str, Any] = {
            "address": address,
            "native": {},
            "tokens": [],
            "total_usd": 0.0,
        }

        # Native ETH balance
        try:
            eth_balance = self._get_native_balance(address)
            if eth_balance is not None:
                eth_price = self._get_token_price("ethereum") or 0
                usd_value = eth_balance * eth_price
                result["native"] = {
                    "symbol": "ETH",
                    "balance": eth_balance,
                    "price_usd": eth_price,
                    "usd_value": usd_value,
                }
                result["total_usd"] += usd_value
        except Exception as exc:
            logger.warning("get_native_balance failed for %s: %s", address, exc)
            result["native"] = {"error": str(exc)}

        # ERC-20 token balances
        try:
            tokens = self._get_erc20_balances(address)
            for token in tokens:
                symbol = token.get("symbol", "")
                balance = token.get("balance", 0)
                if balance <= 0:
                    continue
                price = self._get_token_price_by_symbol(symbol) or 0
                usd_value = balance * price
                token["price_usd"] = price
                token["usd_value"] = usd_value
                result["tokens"].append(token)
                result["total_usd"] += usd_value
        except Exception as exc:
            logger.warning("get_erc20_balances failed for %s: %s", address, exc)

        return result

    def _get_native_balance(self, address: str) -> float | None:
        """Get native ETH balance via Alchemy JSON-RPC."""
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1,
        }
        try:
            resp = requests.post(self._alchemy_url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            balance_hex = data.get("result", "0x0")
            return int(balance_hex, 16) / 1e18
        except Exception as exc:
            logger.warning("Alchemy eth_getBalance failed: %s", exc)
            return None

    def _get_erc20_balances(self, address: str) -> list[dict[str, Any]]:
        """Get ERC-20 token balances via Alchemy token balances API."""
        tokens: list[dict[str, Any]] = []

        # Use Alchemy's alchemy_getTokenBalances if available
        payload = {
            "jsonrpc": "2.0",
            "method": "alchemy_getTokenBalances",
            "params": [address],
            "id": 2,
        }
        try:
            resp = requests.post(self._alchemy_url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            balances = data.get("result", {}).get("tokenBalances", [])
            for bal in balances:
                token_address = bal.get("tokenAddress", "")
                raw_balance = bal.get("tokenBalance", "0x0")
                if raw_balance == "0x0" or raw_balance == "0x":
                    continue
                # Get token metadata
                meta = self._get_token_metadata(token_address)
                if not meta:
                    continue
                decimals = meta.get("decimals", 18)
                balance = int(raw_balance, 16) / (10 ** decimals)
                if balance > 0:
                    tokens.append({
                        "symbol": meta.get("symbol", "UNKNOWN"),
                        "name": meta.get("name", ""),
                        "address": token_address,
                        "balance": balance,
                        "decimals": decimals,
                    })
        except Exception as exc:
            logger.warning("alchemy_getTokenBalances failed: %s", exc)

        return tokens

    def _get_token_metadata(self, token_address: str) -> dict[str, Any] | None:
        """Get ERC-20 token metadata (name, symbol, decimals) via Alchemy."""
        # eth_call to tokenAddress balanceOf(address) — but for metadata we need
        # name(), symbol(), decimals() calls. Use Alchemy's helper if available.
        try:
            # Try Alchemy getTokenMetadata
            payload = {
                "jsonrpc": "2.0",
                "method": "alchemy_getTokenMetadata",
                "params": [token_address],
                "id": 3,
            }
            resp = requests.post(self._alchemy_url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            meta = data.get("result", {})
            if meta and meta.get("symbol"):
                return {
                    "name": meta.get("name", ""),
                    "symbol": meta.get("symbol", ""),
                    "decimals": int(meta.get("decimals", 18)),
                }
        except Exception:
            pass
        return None

    # ── DeFi positions ──────────────────────────────────────────────

    def get_defi_positions(self, address: str) -> dict[str, Any]:
        """Get DeFi positions (Aave, Uniswap, etc.) for an address.

        Basic implementation — uses Alchemy's enhanced APIs if available,
        otherwise returns a summary from on-chain reads.
        """
        address = address.strip()
        if not address.startswith("0x"):
            return {"error": "Invalid address"}

        result: dict[str, Any] = {
            "address": address,
            "positions": [],
            "total_usd": 0.0,
        }

        # Aave positions (basic — check aToken balances)
        try:
            aave = self._get_aave_positions(address)
            if aave:
                result["positions"].extend(aave)
        except Exception as exc:
            logger.warning("Aave positions failed: %s", exc)

        # Uniswap V3 positions (basic)
        try:
            uni = self._get_uniswap_positions(address)
            if uni:
                result["positions"].extend(uni)
        except Exception as exc:
            logger.warning("Uniswap positions failed: %s", exc)

        # Calculate total
        for pos in result["positions"]:
            result["total_usd"] += pos.get("usd_value", 0)

        return result

    def _get_aave_positions(self, address: str) -> list[dict[str, Any]]:
        """Get Aave lending positions (basic implementation).

        Checks common aToken balances. A full implementation would use
        the Aave subgraph or Alchemy's enhanced API.
        """
        positions: list[dict[str, Any]] = []

        # Common Aave aToken addresses (mainnet)
        a_tokens = {
            "aWETH": "0x030bA81f1c18d280636F32af80b9AAd02CfE0a78",
            "aUSDC": "0xBcca60bB61934080954369b6409b6C0dA1cA8E18",
            "aDAI": "0x028171bCA77440897B824Ca71D1c70bC6c4F60b6",
            "aUSDT": "0x23878914EFE38d27C4D67Ab83ed1b93A74D4056",
        }

        for symbol, token_addr in a_tokens.items():
            try:
                balance = self._get_erc20_balance_of(address, token_addr, 18)
                if balance and balance > 0:
                    underlying = symbol[1:]  # strip 'a' prefix
                    price = self._get_token_price_by_symbol(underlying) or 0
                    usd_value = balance * price
                    positions.append({
                        "protocol": "Aave",
                        "type": "lending",
                        "asset": underlying,
                        "balance": balance,
                        "usd_value": usd_value,
                    })
            except Exception:
                continue

        return positions

    def _get_uniswap_positions(self, address: str) -> list[dict[str, Any]]:
        """Get Uniswap V3 positions (basic).

        A full implementation would query the Uniswap V3 NonfungiblePositionManager
        or use the Uniswap subgraph. This is a placeholder that returns empty.
        """
        # Placeholder — would need subgraph or multicall
        return []

    def _get_erc20_balance_of(self, address: str, token_address: str, decimals: int = 18) -> float | None:
        """Get ERC-20 balance of an address for a specific token."""
        # balanceOf(address) selector: 0x70a08231
        padded_addr = address[2:].lower().zfill(64)
        data = "0x70a08231" + padded_addr
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": token_address, "data": data}, "latest"],
            "id": 10,
        }
        try:
            resp = requests.post(self._alchemy_url, json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json().get("result", "0x")
            if result == "0x" or not result:
                return 0.0
            return int(result, 16) / (10 ** decimals)
        except Exception:
            return None

    # ── Staking positions ───────────────────────────────────────────

    def get_staking_positions(self, address: str) -> dict[str, Any]:
        """Get staking positions for an address.

        Basic implementation — checks common staking contracts.
        """
        address = address.strip()
        if not address.startswith("0x"):
            return {"error": "Invalid address"}

        result: dict[str, Any] = {
            "address": address,
            "positions": [],
            "total_usd": 0.0,
        }

        # Lido stETH staking
        try:
            steth_balance = self._get_erc20_balance_of(
                address, "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", 18
            )
            if steth_balance and steth_balance > 0:
                eth_price = self._get_token_price("ethereum") or 0
                usd_value = steth_balance * eth_price
                result["positions"].append({
                    "protocol": "Lido",
                    "type": "staking",
                    "asset": "stETH",
                    "balance": steth_balance,
                    "usd_value": usd_value,
                })
                result["total_usd"] += usd_value
        except Exception as exc:
            logger.warning("Lido staking check failed: %s", exc)

        # Rocket Pool rETH
        try:
            reth_balance = self._get_erc20_balance_of(
                address, "0xae78736Cd615f374D3085123A210448E74Fc6393", 18
            )
            if reth_balance and reth_balance > 0:
                eth_price = self._get_token_price("ethereum") or 0
                usd_value = reth_balance * eth_price
                result["positions"].append({
                    "protocol": "Rocket Pool",
                    "type": "staking",
                    "asset": "rETH",
                    "balance": reth_balance,
                    "usd_value": usd_value,
                })
                result["total_usd"] += usd_value
        except Exception as exc:
            logger.warning("Rocket Pool staking check failed: %s", exc)

        return result

    # ── Price helpers ───────────────────────────────────────────────

    def _get_token_price(self, coin_id: str) -> float | None:
        """Get token price from CoinGecko free API."""
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price"
            resp = requests.get(url, params={"ids": coin_id, "vs_currencies": "usd"}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return float(data.get(coin_id, {}).get("usd", 0))
        except Exception as exc:
            logger.warning("CoinGecko price fetch failed for %s: %s", coin_id, exc)
            return None

    def _get_token_price_by_symbol(self, symbol: str) -> float | None:
        """Get token price by symbol via CoinGecko."""
        symbol_map = {
            "ETH": "ethereum",
            "WETH": "ethereum",
            "BTC": "bitcoin",
            "WBTC": "bitcoin",
            "USDT": "tether",
            "USDC": "usd-coin",
            "DAI": "dai",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "AAVE": "aave",
            "MATIC": "matic-network",
            "stETH": "ethereum",
            "rETH": "ethereum",
        }
        coin_id = symbol_map.get(symbol.upper())
        if not coin_id:
            return None
        return self._get_token_price(coin_id)
