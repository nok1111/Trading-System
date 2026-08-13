"""Rate limiting configuration using slowapi.

Limits are applied per-IP (get_remote_address) and are in-memory by default.
For multi-instance deployments, consider configuring a Redis storage backend.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Limit presets (requests per minute)
RATE_AUTH = "30/minute"       # login, register, license validation
RATE_TRADE = "60/minute"      # place orders, cancel, OCO
RATE_READ = "120/minute"      # GET endpoints (positions, orders, balance)
RATE_AI = "20/minute"         # AI agent start/stop/execute
RATE_INTEL = "30/minute"      # intelligence, backtest
RATE_SOCIAL = "60/minute"     # social signals, follow
RATE_BOTS = "30/minute"       # grid/DCA bot management
RATE_SETTINGS = "30/minute"   # settings, watchlist
RATE_DEFAULT = "120/minute"   # fallback for unclassified endpoints
