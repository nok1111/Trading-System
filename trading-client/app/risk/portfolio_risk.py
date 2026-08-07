"""Portfolio-level risk management: correlation, VaR, exposure limits.

Extends the per-position risk system with portfolio-wide checks:
- Correlation matrix between open positions
- Value at Risk (VaR) — how much can be lost in the worst 5% of cases
- Exposure limits by category (majors, memes, DeFi, etc.)
- Concentration warnings (too much in correlated assets)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Asset Categories ─────────────────────────────────────────────────────────

ASSET_CATEGORIES: dict[str, list[str]] = {
    "major": [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "LTC", "AVAX",
    ],
    "large_cap": [
        "LINK", "DOT", "MATIC", "ATOM", "NEAR", "ARB", "OP", "APT", "FIL", "INJ",
    ],
    "mid_cap": [
        "SUI", "SEI", "TIA", "RNDR", "FET", "WLD", "ORDI", "TON", "JUP", "PYTH",
    ],
    "meme": [
        "PEPE", "SHIB", "WIF", "FLOKI", "BONK",
    ],
}

# Exposure limits per category (as % of total portfolio)
CATEGORY_EXPOSURE_LIMITS: dict[str, float] = {
    "major": 60.0,      # max 60% in majors
    "large_cap": 40.0,  # max 40% in large caps
    "mid_cap": 25.0,    # max 25% in mid caps
    "meme": 15.0,       # max 15% in memes
}

# Max correlation allowed for new positions
MAX_CORRELATION_THRESHOLD = 0.85


def get_asset_category(symbol: str) -> str:
    """Get the category for a symbol (e.g. BTCUSDT -> major)."""
    base = symbol.replace("USDT", "").replace("USDC", "").replace("/", "")
    for category, assets in ASSET_CATEGORIES.items():
        if base.upper() in assets:
            return category
    return "other"


def _normalize_symbol(symbol: str) -> str:
    """Extract base asset from symbol (BTCUSDT -> BTC, BTC/USDT -> BTC)."""
    if "/" in symbol:
        return symbol.split("/")[0].upper()
    return symbol.replace("USDT", "").replace("USDC", "").upper()


# ─── Correlation Matrix ───────────────────────────────────────────────────────


def fetch_correlation_matrix(
    symbols: list[str],
    interval: str = "1d",
    limit: int = 90,
) -> pd.DataFrame:
    """Fetch historical returns and compute correlation matrix.

    Args:
        symbols: List of trading symbols (e.g. ["BTCUSDT", "ETHUSDT"])
        interval: Kline interval for historical data
        limit: Number of candles to use (90 days = ~3 months)

    Returns:
        Correlation matrix as DataFrame
    """
    if len(symbols) < 2:
        return pd.DataFrame()

    returns_data: dict[str, pd.Series] = {}

    for sym in symbols:
        try:
            resp = httpx.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": sym.upper(), "interval": interval, "limit": limit},
                timeout=10,
            )
            resp.raise_for_status()
            raw = resp.json()
            closes = [float(c[4]) for c in raw]  # index 4 = close
            if len(closes) < 2:
                continue
            base = _normalize_symbol(sym)
            returns = pd.Series(closes).pct_change().dropna()
            returns_data[base] = returns
        except Exception as exc:
            logger.warning("Failed to fetch %s for correlation: %s", sym, exc)

    if len(returns_data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(returns_data)
    return df.corr()


# ─── Value at Risk (VaR) ──────────────────────────────────────────────────────


@dataclass
class VaRResult:
    """Value at Risk calculation result."""

    var_95: float  # 95% VaR — max loss in normal 95% of cases
    var_99: float  # 99% VaR — max loss in extreme 99% of cases
    cvar_95: float  # Conditional VaR (Expected Shortfall) — avg loss beyond 95%
    portfolio_value: float
    method: str = "historical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "var_95_pct": round(self.var_95 / self.portfolio_value * 100, 2) if self.portfolio_value > 0 else 0,
            "var_99_pct": round(self.var_99 / self.portfolio_value * 100, 2) if self.portfolio_value > 0 else 0,
            "cvar_95_pct": round(self.cvar_95 / self.portfolio_value * 100, 2) if self.portfolio_value > 0 else 0,
            "var_95_usd": round(self.var_95, 2),
            "var_99_usd": round(self.var_99, 2),
            "cvar_95_usd": round(self.cvar_95, 2),
            "portfolio_value": round(self.portfolio_value, 2),
            "method": self.method,
        }


def calculate_var(
    positions: list[dict],
    portfolio_value: float,
    confidence: float = 0.95,
    lookback: int = 90,
) -> VaRResult:
    """Calculate Value at Risk using historical simulation.

    Args:
        positions: List of open positions with 'symbol' and 'value' (USD)
        portfolio_value: Total portfolio value in USD
        confidence: Confidence level (0.95 or 0.99)
        lookback: Days of historical data to use

    Returns:
        VaRResult with 95% VaR, 99% VaR, and Conditional VaR
    """
    if not positions or portfolio_value <= 0:
        return VaRResult(var_95=0, var_99=0, cvar_95=0, portfolio_value=portfolio_value)

    # Fetch historical returns for each position
    portfolio_returns: list[float] = []

    # Get daily returns for each asset, weighted by position size
    all_returns: dict[str, np.ndarray] = {}
    total_weight = 0.0

    for pos in positions:
        sym = pos.get("symbol", "")
        value = float(pos.get("value", 0))
        if value <= 0 or not sym:
            continue
        weight = value / portfolio_value
        total_weight += weight

        try:
            resp = httpx.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": sym.upper().replace("/", ""), "interval": "1d", "limit": lookback},
                timeout=10,
            )
            resp.raise_for_status()
            raw = resp.json()
            closes = np.array([float(c[4]) for c in raw])
            if len(closes) < 2:
                continue
            returns = np.diff(closes) / closes[:-1]
            all_returns[sym] = returns * weight
        except Exception as exc:
            logger.warning("Failed to fetch %s for VaR: %s", sym, exc)

    if not all_returns:
        return VaRResult(var_95=0, var_99=0, cvar_95=0, portfolio_value=portfolio_value)

    # Align all return arrays to the shortest length
    min_len = min(len(r) for r in all_returns.values())
    portfolio_daily_returns = np.zeros(min_len)
    for returns in all_returns.values():
        portfolio_daily_returns += returns[-min_len:]

    # Historical VaR: the loss at the (1-confidence) percentile
    percentile_5 = np.percentile(portfolio_daily_returns, 5)  # worst 5%
    percentile_1 = np.percentile(portfolio_daily_returns, 1)  # worst 1%

    var_95 = abs(percentile_5 * portfolio_value)
    var_99 = abs(percentile_1 * portfolio_value)

    # CVaR (Expected Shortfall): average of losses beyond the 5% threshold
    tail_losses = portfolio_daily_returns[portfolio_daily_returns <= percentile_5]
    cvar_95 = abs(np.mean(tail_losses) * portfolio_value) if len(tail_losses) > 0 else var_95

    return VaRResult(
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        portfolio_value=portfolio_value,
    )


# ─── Portfolio Risk Assessment ────────────────────────────────────────────────


@dataclass
class PortfolioRiskAssessment:
    """Full portfolio risk assessment."""

    total_exposure: float
    max_single_position_pct: float
    category_exposure: dict[str, float]
    category_limits: dict[str, float]
    category_warnings: list[str]
    correlation_warnings: list[str]
    correlation_matrix: dict[str, dict[str, float]]
    avg_correlation: float
    var: VaRResult | None
    risk_score: float  # 0-100, higher = riskier
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_exposure": round(self.total_exposure, 2),
            "max_single_position_pct": round(self.max_single_position_pct, 2),
            "category_exposure": {k: round(v, 2) for k, v in self.category_exposure.items()},
            "category_limits": self.category_limits,
            "category_warnings": self.category_warnings,
            "correlation_warnings": self.correlation_warnings,
            "correlation_matrix": {
                k: {k2: round(v2, 3) for k2, v2 in v.items()}
                for k, v in self.correlation_matrix.items()
            },
            "avg_correlation": round(self.avg_correlation, 3),
            "var": self.var.to_dict() if self.var else None,
            "risk_score": round(self.risk_score, 1),
            "recommendations": self.recommendations,
        }


def assess_portfolio_risk(
    positions: list[dict],
    portfolio_value: float,
    fetch_correlation: bool = True,
) -> PortfolioRiskAssessment:
    """Assess portfolio-level risk.

    Args:
        positions: List of open positions with 'symbol' and 'value' (USD)
        portfolio_value: Total portfolio value in USD
        fetch_correlation: Whether to fetch live correlation data (network call)

    Returns:
        PortfolioRiskAssessment with all risk metrics
    """
    category_exposure: dict[str, float] = {}
    category_warnings: list[str] = []
    correlation_warnings: list[str] = []
    recommendations: list[str] = []
    max_single_pct = 0.0

    if not positions:
        return PortfolioRiskAssessment(
            total_exposure=0,
            max_single_position_pct=0,
            category_exposure={},
            category_limits=CATEGORY_EXPOSURE_LIMITS,
            category_warnings=[],
            correlation_warnings=[],
            correlation_matrix={},
            avg_correlation=0,
            var=None,
            risk_score=0,
            recommendations=["No hay posiciones abiertas"],
        )

    total_exposure = sum(float(p.get("value", 0)) for p in positions)

    # Per-position exposure
    for pos in positions:
        value = float(pos.get("value", 0))
        pct = (value / portfolio_value * 100) if portfolio_value > 0 else 0
        max_single_pct = max(max_single_pct, pct)

        # Category exposure
        category = get_asset_category(pos.get("symbol", ""))
        category_exposure[category] = category_exposure.get(category, 0) + value

    # Convert to percentages
    category_exposure_pct = {
        k: (v / portfolio_value * 100) if portfolio_value > 0 else 0
        for k, v in category_exposure.items()
    }

    # Check category limits
    for category, exposure_pct in category_exposure_pct.items():
        limit = CATEGORY_EXPOSURE_LIMITS.get(category, 50.0)
        if exposure_pct > limit:
            category_warnings.append(
                f"{category}: {exposure_pct:.1f}% expuesto (limite {limit:.0f}%)"
            )
            recommendations.append(
                f"Reducir exposicion en {category} — esta en {exposure_pct:.1f}% vs limite {limit:.0f}%"
            )

    # Max single position check
    if max_single_pct > 20:
        recommendations.append(
            f"Posicion unica muy grande: {max_single_pct:.1f}% del portfolio — considerar reducir"
        )

    # Correlation analysis
    avg_correlation = 0.0
    corr_matrix_dict: dict[str, dict[str, float]] = {}

    if fetch_correlation and len(positions) >= 2:
        symbols = [p.get("symbol", "") for p in positions if p.get("symbol")]
        try:
            corr_df = fetch_correlation_matrix(symbols)
            if not corr_df.empty:
                # Convert to dict
                for col in corr_df.columns:
                    corr_matrix_dict[col] = {}
                    for idx in corr_df.index:
                        val = corr_df.loc[idx, col]
                        if not np.isnan(val):
                            corr_matrix_dict[col][idx] = float(val)

                # Find high correlations
                upper_tri = corr_df.where(np.triu(np.ones(corr_df.shape), k=1).astype(bool))
                high_corr = upper_tri.stack().sort_values(ascending=False)
                high_corr = high_corr[high_corr > MAX_CORRELATION_THRESHOLD]

                for (asset1, asset2), corr_val in high_corr.items():
                    correlation_warnings.append(
                        f"Alta correlacion {asset1}/{asset2}: {corr_val:.2f}"
                    )

                if not high_corr.empty:
                    recommendations.append(
                        f"Posiciones altamente correlacionadas — diversificar para reducir riesgo"
                    )

                # Average correlation (excluding diagonal)
                off_diag = upper_tri.stack()
                avg_correlation = float(off_diag.mean()) if len(off_diag) > 0 else 0
        except Exception as exc:
            logger.warning("Correlation analysis failed: %s", exc)

    # VaR calculation
    var_result = None
    try:
        var_result = calculate_var(positions, portfolio_value)
    except Exception as exc:
        logger.warning("VaR calculation failed: %s", exc)

    # Risk score (0-100)
    risk_score = 0.0
    # Concentration risk
    risk_score += min(max_single_pct * 1.5, 30)  # up to 30 points
    # Category limit violations
    risk_score += len(category_warnings) * 10  # 10 points per violation
    # Correlation risk
    risk_score += min(len(correlation_warnings) * 8, 20)  # up to 20 points
    # VaR risk
    if var_result and portfolio_value > 0:
        var_pct = var_result.var_95 / portfolio_value * 100
        risk_score += min(var_pct * 2, 30)  # up to 30 points
    risk_score = min(risk_score, 100)

    if not recommendations:
        if risk_score < 30:
            recommendations.append("Portfolio saludable — riesgo bajo")
        elif risk_score < 60:
            recommendations.append("Portfolio moderado — monitorear correlaciones")

    return PortfolioRiskAssessment(
        total_exposure=total_exposure,
        max_single_position_pct=max_single_pct,
        category_exposure=category_exposure_pct,
        category_limits=CATEGORY_EXPOSURE_LIMITS,
        category_warnings=category_warnings,
        correlation_warnings=correlation_warnings,
        correlation_matrix=corr_matrix_dict,
        avg_correlation=avg_correlation,
        var=var_result,
        risk_score=risk_score,
        recommendations=recommendations,
    )
