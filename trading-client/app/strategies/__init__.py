"""Estrategias de trading intercambiables (FASE 2)."""

from app.strategies.strategy import Strategy
from app.strategies.trend_momentum import TrendMomentumConfig, TrendMomentumStrategy
from app.strategies.mean_reversion import MeanReversionConfig, MeanReversionStrategy
from app.strategies.breakout import BreakoutConfig, BreakoutStrategy
from app.strategies.grid import GridConfig, GridStrategy
from app.strategies.macd_momentum import MACDMomentumConfig, MACDMomentumStrategy
from app.strategies.bollinger_squeeze import BollingerSqueezeConfig, BollingerSqueezeStrategy
from app.strategies.supertrend import SupertrendConfig, SupertrendStrategy
from app.strategies.rsi_divergence import RSIDivergenceConfig, RSIDivergenceStrategy

__all__ = [
    "Strategy",
    "TrendMomentumConfig",
    "TrendMomentumStrategy",
    "MeanReversionConfig",
    "MeanReversionStrategy",
    "BreakoutConfig",
    "BreakoutStrategy",
    "GridConfig",
    "GridStrategy",
    "MACDMomentumConfig",
    "MACDMomentumStrategy",
    "BollingerSqueezeConfig",
    "BollingerSqueezeStrategy",
    "SupertrendConfig",
    "SupertrendStrategy",
    "RSIDivergenceConfig",
    "RSIDivergenceStrategy",
]
