"""DEX trader — swap quotes and transaction preparation via 0x API.

Uses the free 0x API (https://api.0x.org/swap/v1/quote) for swap quotes.
No API key needed for basic usage.

Supports:
  - get_swap_quote(token_in, token_out, amount) — quote via 0x API
  - swap_on_uniswap(token_in, token_out, amount, slippage) — prepare swap tx
  - get_pool_info(pool_address) — pool info
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# 0x API base URL (free, no key needed for basic usage)
_0X_API_BASE = "https://api.0x.org/swap/v1"

# Common token addresses on Ethereum mainnet
TOKEN_ADDRESSES: dict[str, str] = {
    "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
}


class DEXTrader:
    """DEX trading via 0x API — quotes and transaction preparation."""

    def __init__(self) -> None:
        pass

    def _resolve_token_address(self, token: str) -> str | None:
        """Resolve a token symbol or address to a valid address."""
        token = token.strip()
        # If it's already an address
        if token.startswith("0x") and len(token) == 42:
            return token
        # Look up in known tokens
        return TOKEN_ADDRESSES.get(token.upper())

    def get_swap_quote(
        self, token_in: str, token_out: str, amount: str | float
    ) -> dict[str, Any]:
        """Get a swap quote via 0x API.

        Args:
            token_in: Token symbol (e.g. "ETH") or address.
            token_out: Token symbol (e.g. "USDC") or address.
            amount: Amount of token_in to swap (in base units, e.g. "1000000000000000000" for 1 ETH).

        Returns:
            Quote dict with price, amounts, and estimated gas.
        """
        sell_token = self._resolve_token_address(token_in)
        buy_token = self._resolve_token_address(token_out)

        if not sell_token:
            return {"error": f"Unknown token: {token_in}"}
        if not buy_token:
            return {"error": f"Unknown token: {token_out}"}

        # Convert amount to string (0x expects sellAmount in base units)
        sell_amount = str(amount)

        params = {
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": sell_amount,
        }

        try:
            resp = requests.get(f"{_0X_API_BASE}/quote", params=params, timeout=15)
            if resp.status_code != 200:
                error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "error": error_data.get("reason", f"0x API returned {resp.status_code}"),
                    "status_code": resp.status_code,
                }

            data = resp.json()
            return {
                "sell_token": data.get("sellToken"),
                "buy_token": data.get("buyToken"),
                "sell_amount": data.get("sellAmount"),
                "buy_amount": data.get("buyAmount"),
                "price": data.get("price"),
                "estimated_gas": data.get("estimatedGas"),
                "gas_price": data.get("gasPrice"),
                "protocol_fee": data.get("protocolFee"),
                "sources": data.get("sources", [])[:5],  # Top 5 liquidity sources
                "allowance_target": data.get("allowanceTarget"),
            }
        except requests.Timeout:
            return {"error": "0x API request timed out"}
        except Exception as exc:
            logger.warning("0x swap quote failed: %s", exc)
            return {"error": str(exc)}

    def swap_on_uniswap(
        self,
        token_in: str,
        token_out: str,
        amount: str | float,
        slippage: float = 0.01,
    ) -> dict[str, Any]:
        """Prepare a swap transaction via 0x API (which routes through Uniswap and others).

        Returns the full transaction data that the user can sign and submit
        from their wallet. Does NOT execute the swap — just prepares it.

        Args:
            token_in: Token symbol or address.
            token_out: Token symbol or address.
            amount: Amount of token_in in base units.
            slippage: Slippage tolerance as a fraction (0.01 = 1%).
        """
        sell_token = self._resolve_token_address(token_in)
        buy_token = self._resolve_token_address(token_out)

        if not sell_token:
            return {"error": f"Unknown token: {token_in}"}
        if not buy_token:
            return {"error": f"Unknown token: {token_out}"}

        sell_amount = str(amount)
        # Convert slippage fraction to basis points for 0x API
        slippage_bps = int(slippage * 10000)

        params = {
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": sell_amount,
            "slippagePercentage": slippage,
        }

        try:
            resp = requests.get(f"{_0X_API_BASE}/swap", params=params, timeout=15)
            if resp.status_code != 200:
                error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "error": error_data.get("reason", f"0x API returned {resp.status_code}"),
                    "status_code": resp.status_code,
                }

            data = resp.json()
            return {
                "to": data.get("to"),
                "from": data.get("from"),
                "value": data.get("value"),
                "data": data.get("data"),
                "gas": data.get("gas"),
                "gas_price": data.get("gasPrice"),
                "sell_token": data.get("sellToken"),
                "buy_token": data.get("buyToken"),
                "sell_amount": data.get("sellAmount"),
                "buy_amount": data.get("buyAmount"),
                "price": data.get("price"),
                "allowance_target": data.get("allowanceTarget"),
                "sources": data.get("sources", [])[:5],
                "note": "Sign and submit this transaction from your wallet to execute the swap.",
            }
        except requests.Timeout:
            return {"error": "0x API request timed out"}
        except Exception as exc:
            logger.warning("0x swap tx preparation failed: %s", exc)
            return {"error": str(exc)}

    def get_pool_info(self, pool_address: str) -> dict[str, Any]:
        """Get pool info for a Uniswap V3 (or other DEX) pool.

        Basic implementation — reads pool contract data via Alchemy/public RPC.
        """
        pool_address = pool_address.strip()
        if not pool_address.startswith("0x") or len(pool_address) != 42:
            return {"error": "Invalid pool address"}

        result: dict[str, Any] = {"pool_address": pool_address}

        # Read token0() — selector: 0x0dfe1681
        token0 = self._eth_call(pool_address, "0dfe1681")
        if token0 and len(token0) >= 66:
            addr0 = "0x" + token0[26:66]
            if addr0 != "0x" + "0" * 40:
                result["token0"] = addr0

        # Read token1() — selector: 0xd21220a7
        token1 = self._eth_call(pool_address, "d21220a7")
        if token1 and len(token1) >= 66:
            addr1 = "0x" + token1[26:66]
            if addr1 != "0x" + "0" * 40:
                result["token1"] = addr1

        # Read fee() — selector: 0xddca3f43 (Uniswap V3)
        fee_raw = self._eth_call(pool_address, "ddca3f43")
        if fee_raw and len(fee_raw) >= 66:
            try:
                fee = int(fee_raw[2:66], 16)
                result["fee"] = fee
                result["fee_pct"] = fee / 10000  # e.g. 3000 -> 0.3%
            except Exception:
                pass

        # Read liquidity() — selector: 0x1a686502
        liquidity_raw = self._eth_call(pool_address, "1a686502")
        if liquidity_raw and len(liquidity_raw) >= 66:
            try:
                result["liquidity"] = int(liquidity_raw[2:66], 16)
            except Exception:
                pass

        # Read slot0() for sqrtPriceX96 and tick — selector: 0x3850c7bd
        slot0_raw = self._eth_call(pool_address, "3850c7bd")
        if slot0_raw and len(slot0_raw) >= 66:
            try:
                sqrt_price = int(slot0_raw[2:66], 16)
                result["sqrt_price_x96"] = sqrt_price
                # Price = (sqrtPriceX96 / 2^96)^2
                if sqrt_price > 0:
                    price = (sqrt_price / (2 ** 96)) ** 2
                    result["price_ratio"] = price
            except Exception:
                pass

        return result

    def _eth_call(self, to: str, data_selector: str) -> str | None:
        """Make an eth_call to a contract."""
        # Use a public RPC fallback
        rpc_url = "https://eth.llamarpc.com"
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": to, "data": "0x" + data_selector}, "latest"],
            "id": 1,
        }
        try:
            resp = requests.post(rpc_url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json().get("result")
        except Exception as exc:
            logger.warning("eth_call failed for %s: %s", to, exc)
            return None
