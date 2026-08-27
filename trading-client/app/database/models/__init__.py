"""Modelos de datos del sistema de trading (Trading Client — sin User)."""

from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.agent_log import AgentLog
from app.database.models.alvora_config import AlvoraConfig
from app.database.models.alvora_conversation import AlvoraConversation
from app.database.models.alvora_message import AlvoraMessage
from app.database.models.agent_session import AgentSession
from app.database.models.ai_recommendation import AIRecommendation
from app.database.models.backtest_run import BacktestRun
from app.database.models.broker_account import BrokerAccount
from app.database.models.grid_bot import DCABot, GridBot
from app.database.models.market_bar import MarketBar
from app.database.models.model_version import ModelVersion
from app.database.models.intelligence_analysis import IntelligenceAnalysis
from app.database.models.intelligence_event import IntelligenceEvent
from app.database.models.intelligence_news import IntelligenceNews
from app.database.models.notification import Notification
from app.database.models.order import Order
from app.database.models.order_idempotency import OrderIdempotencyRecord
from app.database.models.order_reconciliation import OrderReconciliation
from app.database.models.portfolio_guard_config import PortfolioGuardConfig
from app.database.models.position import Position
from app.database.models.price_alert import PriceAlert
from app.database.models.prediction_record import PredictionRecord
from app.database.models.risk_config import RiskConfig
from app.database.models.risk_event import RiskEvent
from app.database.models.signal import Signal
from app.database.models.social_follow import SocialCopyTrade, SocialFollow
from app.database.models.social_leader import SocialLeader
from app.database.models.social_signal import SocialSignal
from app.database.models.strategy_run import StrategyRun
from app.database.models.system_event import SystemEvent
from app.database.models.tax_report import TaxReport
from app.database.models.strategy_marketplace import (
    StrategyBacktestVerification,
    StrategyListing,
    StrategyReview,
    StrategySubscription,
)
from app.database.models.academy_progress import AcademyProgress
from app.database.models.trade import Trade
from app.database.models.trade_verification import TradeVerification
from app.database.models.user_settings import UserSettings
from app.database.models.user_profile import UserProfile
from app.database.models.user_preference import UserPreference
from app.database.models.watchlist import Watchlist

__all__ = [
    "AccountSnapshot",
    "AgentLog",
    "AlvoraConfig",
    "AlvoraConversation",
    "AlvoraMessage",
    "AgentSession",
    "AIRecommendation",
    "BacktestRun",
    "BrokerAccount",
    "DCABot",
    "GridBot",
    "MarketBar",
    "ModelVersion",
    "IntelligenceAnalysis",
    "IntelligenceEvent",
    "IntelligenceNews",
    "Notification",
    "Order",
    "OrderIdempotencyRecord",
    "OrderReconciliation",
    "PortfolioGuardConfig",
    "Position",
    "PriceAlert",
    "PredictionRecord",
    "RiskConfig",
    "RiskEvent",
    "Signal",
    "SocialCopyTrade",
    "SocialFollow",
    "SocialLeader",
    "SocialSignal",
    "StrategyRun",
    "SystemEvent",
    "TaxReport",
    "StrategyBacktestVerification",
    "StrategyListing",
    "StrategyReview",
    "StrategySubscription",
    "AcademyProgress",
    "Trade",
    "TradeVerification",
    "UserSettings",
    "UserProfile",
    "UserPreference",
    "Watchlist",
]
