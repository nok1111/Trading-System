"""DeFi / On-Chain API routes.

Endpoints:
  GET   /api/defi/wallet/{address}/balances  — wallet balances (auth)
  GET   /api/defi/wallet/{address}/positions — DeFi positions (auth)
  POST  /api/defi/wallet/connect             — connect wallet (auth)
  GET   /api/defi/swap/quote                 — swap quote (auth)
  GET   /api/defi/tvl                        — TVL global
  GET   /api/defi/gas                        — gas tracker
  GET   /api/defi/whales                     — whale movements
  GET   /api/defi/exchange-flows             — exchange flows
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.defi.wallet_manager import WalletManager
from app.defi.dex_trader import DEXTrader
from app.defi.onchain_analytics import OnChainAnalytics
from app.services.auth import LocalUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/defi", tags=["defi"])

# Singleton instances
_wallet_mgr = WalletManager()
_dex_trader = DEXTrader()
_analytics = OnChainAnalytics()


class ConnectWalletRequest(BaseModel):
    address: str
    label: str = ""


@router.post("/wallet/connect")
def connect_wallet(
    req: ConnectWalletRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Connect an on-chain wallet to the user's account."""
    return _wallet_mgr.connect_wallet(current_user.id, req.address, req.label)


@router.get("/wallet/{address}/balances")
def get_wallet_balances(
    address: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get ERC-20 + native ETH balances for a wallet address."""
    return _wallet_mgr.get_wallet_balances(address)


@router.get("/wallet/{address}/positions")
def get_defi_positions(
    address: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get DeFi positions (Aave, Uniswap, staking) for a wallet address."""
    balances = _wallet_mgr.get_defi_positions(address)
    staking = _wallet_mgr.get_staking_positions(address)
    return {
        "defi": balances,
        "staking": staking,
    }


@router.get("/swap/quote")
def get_swap_quote(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    token_in: str = Query(..., description="Token symbol or address to sell"),
    token_out: str = Query(..., description="Token symbol or address to buy"),
    amount: str = Query(..., description="Amount of token_in in base units"),
) -> dict:
    """Get a DEX swap quote via 0x API (free, no key needed)."""
    return _dex_trader.get_swap_quote(token_in, token_out, amount)


@router.get("/swap/prepare")
def prepare_swap(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    token_in: str = Query(...),
    token_out: str = Query(...),
    amount: str = Query(...),
    slippage: float = Query(0.01, ge=0, le=0.5),
) -> dict:
    """Prepare a swap transaction via 0x API. Returns unsigned tx data."""
    return _dex_trader.swap_on_uniswap(token_in, token_out, amount, slippage)


@router.get("/pool/{pool_address}")
def get_pool_info(
    pool_address: str,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get DEX pool info (Uniswap V3 or compatible)."""
    return _dex_trader.get_pool_info(pool_address)


@router.get("/tvl")
def get_defi_tvl(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get global DeFi TVL via DeFiLlama API (free)."""
    return _analytics.get_defi_tvl()


@router.get("/gas")
def get_gas(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get current Ethereum gas prices."""
    return _analytics.get_gas_tracker()


@router.get("/whales")
def get_whales(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get recent whale movements (large transfers)."""
    return _analytics.get_whale_movements()


@router.get("/exchange-flows")
def get_exchange_flows(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get exchange inflows/outflows."""
    return _analytics.get_exchange_flows()


@router.get("/prices")
def get_token_prices(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    symbols: str = Query("BTC,ETH,SOL", description="Comma-separated token symbols"),
) -> dict:
    """Get token prices via CoinGecko free API."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return _analytics.get_token_prices(symbol_list)
