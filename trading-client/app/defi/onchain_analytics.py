"""On-chain analytics — TVL, gas, whale movements, exchange flows, token prices.

Uses free public APIs:
  - DeFiLlama: https://api.llama.fi/v2/chains (TVL)
  - ETH gas: public RPC or etherscan-style APIs
  - Whale Alert: free API (with key) or fallback to on-chain heuristics
  - CoinGecko: https://api.coingecko.com/api/v3 (token prices)

All APIs are free. Handles errors gracefully.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Free API endpoints
DEFILLAMA_CHAINS_URL = "https://api.llama.fi/v2/chains"
DEFILLAMA_PROTOCOLS_URL = "https://api.llama.fi/protocols"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
ETH_GAS_STATION_URL = "https://ethgasstation.info/api/ethgasAPI.json"
BLOCKNATIVE_GAS_URL = "https://api.blocknative.com/gasprices/blockprices"
LLAMANODES_RPC = "https://eth.llamarpc.com"


class OnChainAnalytics:
    """On-chain analytics aggregator using free public APIs."""

    def __init__(self) -> None:
        pass

    # ── TVL ─────────────────────────────────────────────────────────

    def get_defi_tvl(self) -> dict[str, Any]:
        """Get DeFi TVL across all chains via DeFiLlama API (free)."""
        try:
            resp = requests.get(DEFILLAMA_CHAINS_URL, timeout=15)
            resp.raise_for_status()
            chains = resp.json()

            total_tvl = sum(c.get("tvl", 0) for c in chains if c.get("tvl"))
            top_chains = sorted(
                [c for c in chains if c.get("tvl")],
                key=lambda c: c.get("tvl", 0),
                reverse=True,
            )[:15]

            return {
                "total_tvl_usd": total_tvl,
                "chains": [
                    {
                        "name": c.get("name", ""),
                        "tvl_usd": c.get("tvl", 0),
                        "token_symbol": c.get("tokenSymbol", ""),
                        "chain_id": c.get("chainId"),
                    }
                    for c in top_chains
                ],
                "chain_count": len(chains),
            }
        except requests.Timeout:
            return {"error": "DeFiLlama API request timed out"}
        except Exception as exc:
            logger.warning("get_defi_tvl failed: %s", exc)
            return {"error": str(exc)}

    # ── Gas tracker ─────────────────────────────────────────────────

    def get_gas_tracker(self) -> dict[str, Any]:
        """Get current Ethereum gas prices.

        Tries ETH gas station first, falls back to parsing latest block
        gas price from a public RPC.
        """
        # Try ETH gas station
        try:
            resp = requests.get(ETH_GAS_STATION_URL, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # ETH gas station returns prices in 10x Gwei (divide by 10)
                return {
                    "fast": data.get("fast", 0) / 10,
                    "fastest": data.get("fastest", 0) / 10,
                    "safe_low": data.get("safeLow", 0) / 10,
                    "average": data.get("average", 0) / 10,
                    "block_num": data.get("blockNum"),
                    "unit": "Gwei",
                    "source": "ethgasstation",
                }
        except Exception as exc:
            logger.warning("ETH gas station failed: %s", exc)

        # Fallback: get gas price from latest block via public RPC
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBlockByNumber",
                "params": ["latest", False],
                "id": 1,
            }
            resp = requests.post(LLAMANODES_RPC, json=payload, timeout=10)
            resp.raise_for_status()
            block = resp.json().get("result", {})
            base_fee_hex = block.get("baseFeePerGas", "0x0")
            base_fee = int(base_fee_hex, 16) / 1e9  # wei to Gwei

            return {
                "base_fee": base_fee,
                "unit": "Gwei",
                "source": "rpc_latest_block",
                "block_number": int(block.get("number", "0x0"), 16),
            }
        except Exception as exc:
            logger.warning("RPC gas fallback failed: %s", exc)
            return {"error": f"Could not fetch gas prices: {exc}"}

    # ── Whale movements ─────────────────────────────────────────────

    def get_whale_movements(self) -> dict[str, Any]:
        """Get recent large token transfers (whale movements).

        Uses Whale Alert API if a key is configured, otherwise falls back
        to a basic on-chain heuristic using public data.
        """
        from app.config import get_settings

        settings = get_settings()
        whale_api_key = getattr(settings, "WHALE_ALERT_API_KEY", None)

        if whale_api_key:
            try:
                import time

                url = "https://api.whale-alert.io/v1/transactions"
                params = {
                    "api_key": whale_api_key,
                    "min": 500000,  # min USD value
                    "start": int(time.time()) - 3600,  # last 1 hour
                    "limit": 50,
                }
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "transactions": data.get("transactions", []),
                        "count": data.get("count", 0),
                        "source": "whale_alert",
                    }
            except Exception as exc:
                logger.warning("Whale Alert API failed: %s", exc)

        # Fallback: return a summary based on DeFiLlama protocol flows
        try:
            resp = requests.get(DEFILLAMA_PROTOCOLS_URL, timeout=15)
            resp.raise_for_status()
            protocols = resp.json()
            # Get protocols with largest 24h volume change as a proxy
            top = sorted(
                protocols,
                key=lambda p: abs(p.get("change_1h", 0)),
                reverse=True,
            )[:10]
            return {
                "transactions": [
                    {
                        "protocol": p.get("name", ""),
                        "chain": p.get("chain", ""),
                        "tvl_usd": p.get("tvl", 0),
                        "change_1h_pct": p.get("change_1h", 0),
                        "change_1d_pct": p.get("change_1d", 0),
                    }
                    for p in top
                ],
                "count": len(top),
                "source": "defillama_protocols",
                "note": "Whale Alert API not configured — showing protocol flow changes instead.",
            }
        except Exception as exc:
            logger.warning("Whale movements fallback failed: %s", exc)
            return {"error": f"Could not fetch whale movements: {exc}"}

    # ── Exchange flows ──────────────────────────────────────────────

    def get_exchange_flows(self) -> dict[str, Any]:
        """Get exchange inflows/outflows.

        Basic implementation — uses DeFiLlama CEX data if available,
        otherwise returns a summary from protocol data.
        """
        try:
            # DeFiLlama CEX transparency endpoint
            url = "https://api.llama.fi/overview/CEX"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "total_cex_tvl": data.get("currentChainTvls", {}).get("CEX", 0),
                    "source": "defillama_cex",
                    "data": data.get("currentChainTvls", {}),
                }
        except Exception as exc:
            logger.warning("Exchange flows fetch failed: %s", exc)

        # Fallback: estimate from chain TVL changes
        try:
            resp = requests.get(DEFILLAMA_CHAINS_URL, timeout=15)
            resp.raise_for_status()
            chains = resp.json()
            # Sum up major exchange chains
            exchange_chains = [c for c in chains if c.get("name", "").lower() in ("ethereum", "bitcoin", "tron")]
            return {
                "source": "defillama_chains_estimate",
                "flows": [
                    {
                        "chain": c.get("name", ""),
                        "tvl_usd": c.get("tvl", 0),
                    }
                    for c in exchange_chains
                ],
                "note": "CEX-specific flow data not available — showing chain TVL instead.",
            }
        except Exception as exc:
            return {"error": f"Could not fetch exchange flows: {exc}"}

    # ── Token prices ────────────────────────────────────────────────

    def get_token_prices(self, symbols: list[str]) -> dict[str, Any]:
        """Get token prices via CoinGecko free API.

        Args:
            symbols: List of token symbols (e.g. ["BTC", "ETH", "SOL"]).

        Returns:
            Dict mapping symbol -> price_usd.
        """
        # Map common symbols to CoinGecko coin IDs
        symbol_to_id: dict[str, str] = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "BNB": "binancecoin",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "AVAX": "avalanche-2",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "ATOM": "cosmos",
            "LTC": "litecoin",
            "DOGE": "dogecoin",
            "TRX": "tron",
            "SHIB": "shiba-inu",
            "PEPE": "pepe",
            "ARB": "arbitrum",
            "OP": "optimism",
            "NEAR": "near",
            "APT": "aptos",
            "SUI": "sui",
            "SEI": "sei-network",
            "TIA": "celestia",
            "INJ": "injective-protocol",
            "FET": "fetch-ai",
            "RNDR": "render-token",
            "WLD": "worldcoin-wld",
            "TON": "the-open-network",
            "AAVE": "aave",
            "DAI": "dai",
            "USDT": "tether",
            "USDC": "usd-coin",
        }

        coin_ids = []
        id_to_symbol: dict[str, str] = {}
        for sym in symbols:
            sym_upper = sym.upper()
            coin_id = symbol_to_id.get(sym_upper)
            if coin_id:
                coin_ids.append(coin_id)
                id_to_symbol[coin_id] = sym_upper

        if not coin_ids:
            return {"prices": {}, "error": "No recognized symbols"}

        try:
            url = f"{COINGECKO_BASE}/simple/price"
            params = {
                "ids": ",".join(coin_ids),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_market_cap": "true",
            }
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            prices: dict[str, Any] = {}
            for coin_id, price_data in data.items():
                symbol = id_to_symbol.get(coin_id, coin_id)
                prices[symbol] = {
                    "price_usd": price_data.get("usd", 0),
                    "change_24h_pct": price_data.get("usd_24h_change", 0),
                    "market_cap_usd": price_data.get("usd_market_cap", 0),
                }

            return {"prices": prices, "source": "coingecko"}
        except requests.Timeout:
            return {"error": "CoinGecko API request timed out"}
        except Exception as exc:
            logger.warning("get_token_prices failed: %s", exc)
            return {"error": str(exc)}
