"""Scalp Engine — ranking de volatilidad + filtro IA + 1 posición futures.

Señales de entrada/salida son deterministas (ATR, volumen, momentum).
La IA local solo confirma 3 candidatos cada ai_refresh_sec con un JSON corto.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.database.models.grid_bot import ScalpBot, ScalpBotLog
from app.database.session import SessionLocal

logger = logging.getLogger(__name__)

_UNIVERSE_TTL = 60.0
_KLINE_TTL = 25.0
_AI_SYSTEM = (
    "Scalp filter. Reply JSON only: {\"pick\":\"SYM\",\"side\":\"long|short|skip\",\"conf\":0.0}. "
    "No text."
)

# In-process caches (shared across scheduler ticks)
_universe_cache: dict[str, Any] = {"ts": 0.0, "rows": []}
_kline_cache: dict[str, tuple[float, list]] = {}
_ai_cache: dict[int, dict[str, Any]] = {}  # bot_id -> {ts, pick, side, conf}
_hedge_cache: dict[int, bool] = {}  # user_id -> dual-side (hedge) mode


def atr_from_ohlc(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    """Wilder ATR. Returns 0 if not enough bars."""
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0
    trs: list[float] = []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return 0.0
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def score_symbol(
    atr_pct: float,
    volume: float,
    return_5m: float,
    vol_ratio: float = 1.0,
) -> float:
    """Deterministic volatility score. Higher = better scalp candidate."""
    if atr_pct <= 0 or volume <= 0:
        return 0.0
    return atr_pct * math.log1p(volume) * (1.0 + abs(return_5m)) * max(vol_ratio, 0.1)


def parse_ai_pick(raw: str) -> dict[str, Any] | None:
    """Extract {pick, side, conf} from model output. None if unusable."""
    if not raw:
        return None
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    pick = str(data.get("pick") or "").upper().replace("/", "")
    side = str(data.get("side") or "skip").lower()
    if side not in ("long", "short", "skip"):
        side = "skip"
    try:
        conf = float(data.get("conf") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if not pick:
        return None
    return {"pick": pick, "side": side, "conf": conf}


def heartbeat_expired(last_heartbeat_at: datetime | None, now: datetime | None = None, timeout_sec: int = 20) -> bool:
    if last_heartbeat_at is None:
        return True
    now = now or datetime.now(tz=UTC)
    hb = last_heartbeat_at
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=UTC)
    return (now - hb).total_seconds() > timeout_sec


def _log(
    session,
    bot_id: int,
    event: str,
    message: str,
    *,
    level: str = "info",
    symbol: str | None = None,
    side: str | None = None,
    price: float | None = None,
    quantity: float | None = None,
    pnl: float | None = None,
) -> None:
    entry = ScalpBotLog(
        bot_id=bot_id,
        timestamp=datetime.now(tz=UTC),
        level=level,
        event=event,
        symbol=symbol,
        side=side,
        price=Decimal(str(price)) if price is not None else None,
        quantity=Decimal(str(quantity)) if quantity is not None else None,
        pnl=Decimal(str(pnl)) if pnl is not None else None,
        message=message[:500],
    )
    session.add(entry)
    # Keep last 400 logs
    try:
        ids = (
            session.query(ScalpBotLog.id)
            .filter(ScalpBotLog.bot_id == bot_id)
            .order_by(ScalpBotLog.id.desc())
            .offset(400)
            .all()
        )
        if ids:
            session.query(ScalpBotLog).filter(ScalpBotLog.id.in_([r[0] for r in ids])).delete(synchronize_session=False)
    except Exception:
        pass


def _fetch_universe(limit: int = 30) -> list[dict[str, Any]]:
    now = time.monotonic()
    if now - _universe_cache["ts"] < _UNIVERSE_TTL and _universe_cache["rows"]:
        return _universe_cache["rows"]
    try:
        resp = httpx.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("scalp universe fetch failed: %s", exc)
        return _universe_cache["rows"] or []

    rows: list[dict[str, Any]] = []
    for t in data:
        sym = t.get("symbol") or ""
        if not sym.endswith("USDT") or "_" in sym:
            continue
        if not sym.isascii():
            continue
        try:
            vol = float(t.get("quoteVolume") or 0)
            last = float(t.get("lastPrice") or 0)
            pct = float(t.get("priceChangePercent") or 0)
        except (TypeError, ValueError):
            continue
        if vol <= 0 or last <= 0:
            continue
        rows.append({"symbol": sym, "volume": vol, "price": last, "change_pct": pct})
    rows.sort(key=lambda x: x["volume"], reverse=True)
    rows = rows[:limit]
    _universe_cache["ts"] = now
    _universe_cache["rows"] = rows
    return rows


def _fetch_klines(symbol: str, interval: str = "5m", limit: int = 40) -> list[list]:
    key = f"{symbol}:{interval}:{limit}"
    now = time.monotonic()
    cached = _kline_cache.get(key)
    if cached and now - cached[0] < _KLINE_TTL:
        return cached[1]
    try:
        resp = httpx.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=6.0,
        )
        resp.raise_for_status()
        data = resp.json()
        _kline_cache[key] = (now, data)
        return data
    except Exception as exc:
        logger.warning("scalp klines %s failed: %s", symbol, exc)
        return cached[1] if cached else []


def _rank_universe(min_atr_pct: float, max_spread_bps: float = 8.0) -> list[dict[str, Any]]:
    universe = _fetch_universe(30)
    scored: list[dict[str, Any]] = []
    for row in universe:
        kl = _fetch_klines(row["symbol"], "5m", 40)
        if len(kl) < 20:
            continue
        highs = [float(c[2]) for c in kl]
        lows = [float(c[3]) for c in kl]
        closes = [float(c[4]) for c in kl]
        vols = [float(c[5]) for c in kl]
        price = closes[-1]
        if price <= 0:
            continue
        atr = atr_from_ohlc(highs, lows, closes, 14)
        atr_pct = (atr / price) * 100 if atr > 0 else 0.0
        if atr_pct < min_atr_pct:
            continue
        ret5 = ((closes[-2] / closes[-3]) - 1) * 100 if len(closes) > 3 and closes[-3] else 0.0
        # Last CLOSED 5m candle vs average of previous closed bars (current bar is incomplete).
        closed_vols = vols[:-1]
        if len(closed_vols) >= 8:
            avg_vol = sum(closed_vols[-20:-1] if len(closed_vols) > 1 else closed_vols) / max(len(closed_vols[-20:-1] or closed_vols), 1)
            vol_ratio = (closed_vols[-1] / avg_vol) if avg_vol > 0 else 1.0
        else:
            vol_ratio = 1.0
        sc = score_symbol(atr_pct, row["volume"], ret5, vol_ratio)
        scored.append({
            **row,
            "atr_pct": round(atr_pct, 3),
            "return_5m": round(ret5, 3),
            "vol_ratio": round(vol_ratio, 2),
            "score": sc,
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "vols": vols,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _ai_filter(bot: ScalpBot, top3: list[dict[str, Any]]) -> dict[str, Any] | None:
    cached = _ai_cache.get(bot.id)
    now = time.monotonic()
    if cached and now - cached["ts"] < max(int(bot.ai_refresh_sec), 60):
        return cached.get("result")

    lines = []
    for s in top3:
        lines.append(
            f"{s['symbol']} atr={s['atr_pct']} volx={s['vol_ratio']} r5={s['return_5m']:+.2f}"
        )
    user = "\n".join(lines)
    result = None
    try:
        payload = None
        try:
            from app.api.helpers import get_or_create_agent
            agent = get_or_create_agent()
            provider = getattr(agent, "_ai_provider", None) or getattr(agent, "_provider", None)
            if provider is not None and hasattr(provider, "ask"):
                resp = provider.ask(_AI_SYSTEM, user, deep=False)
                payload = getattr(resp, "decision", None)
        except Exception as exc:
            logger.debug("scalp agent provider unavailable: %s", exc)

        if payload is None:
            from app.config import get_settings
            settings = get_settings()
            ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
            ollama_model = getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b")
            r = httpx.post(
                f"{ollama_url.rstrip('/')}/api/chat",
                json={
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": _AI_SYSTEM},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0, "num_predict": 48},
                },
                timeout=12.0,
            )
            if r.status_code == 200:
                payload = r.json().get("message", {}).get("content", "")

        if isinstance(payload, dict):
            result = parse_ai_pick(json.dumps(payload))
        elif isinstance(payload, str):
            result = parse_ai_pick(payload)
    except Exception as exc:
        logger.warning("scalp AI filter failed: %s", exc)
        result = None

    _ai_cache[bot.id] = {"ts": now, "result": result}
    return result


def _entry_signal(candidate: dict[str, Any], side: str) -> tuple[bool, str]:
    """Closed-bar 5m volume + 1m Donchian-3 breakout (includes forming 1m close)."""
    volx = float(candidate.get("vol_ratio") or 0)
    if volx < 1.15:
        return False, f"volumen 5m {volx:.2f}x < 1.15x"
    kl1 = _fetch_klines(candidate["symbol"], "1m", 12)
    if len(kl1) < 6:
        return False, "klines 1m insuficientes"
    highs = [float(c[2]) for c in kl1]
    lows = [float(c[3]) for c in kl1]
    closes = [float(c[4]) for c in kl1]
    opens = [float(c[1]) for c in kl1]
    last = closes[-1]
    # Break last 3 CLOSED 1m extremes (exclude forming bar from the range)
    range_high = max(highs[-4:-1])
    range_low = min(lows[-4:-1])
    body_up = last > opens[-1]
    body_down = last < opens[-1]
    if side == "long":
        if last > range_high and body_up:
            return True, f"breakout 1m high {range_high:.6g} vol={volx:.2f}x"
        return False, f"sin breakout long close={last:.6g} high3={range_high:.6g} vol={volx:.2f}x"
    if side == "short":
        if last < range_low and body_down:
            return True, f"breakout 1m low {range_low:.6g} vol={volx:.2f}x"
        return False, f"sin breakout short close={last:.6g} low3={range_low:.6g} vol={volx:.2f}x"
    return False, "lado inválido"


def _get_futures_adapter(bot: ScalpBot):
    from app.api.helpers import resolve_broker_credentials
    from app.brokers.registry import get_adapter
    from types import SimpleNamespace

    user = SimpleNamespace(id=bot.user_id)
    creds = resolve_broker_credentials(bot.broker_id, user)
    if creds is None:
        return None
    # Binance native adapter is spot-only; use CCXT binance swap for USDT-M
    try:
        from app.brokers.adapters.ccxt_adapter import CCXTAdapter
        return CCXTAdapter(creds, exchange_id="binance", market_type="swap")
    except Exception as exc:
        logger.warning("scalp CCXT futures adapter failed: %s", exc)
        try:
            return get_adapter(bot.broker_id, creds, market_type="swap")
        except Exception:
            return None


def _is_hedge_mode(adapter, user_id: int) -> bool:
    """Binance USDT-M: True if dual-side (hedge). Default False = one-way."""
    cached = _hedge_cache.get(user_id)
    if cached is not None:
        return cached
    dual = False
    try:
        ex = getattr(adapter, "_exchange", None)
        if ex is not None and hasattr(ex, "fapiPrivateGetPositionSideDual"):
            r = ex.fapiPrivateGetPositionSideDual()
            val = (r or {}).get("dualSidePosition")
            dual = val in (True, "true", "True")
    except Exception as exc:
        logger.warning("scalp hedge-mode detect failed (assume one-way): %s", exc)
        dual = False
    _hedge_cache[user_id] = dual
    return dual


def _ccxt_symbol(binance_symbol: str) -> str:
    if "/" in binance_symbol:
        return binance_symbol if ":" in binance_symbol else binance_symbol
    if binance_symbol.endswith("USDT"):
        return f"{binance_symbol[:-4]}/USDT:USDT"
    return binance_symbol


def _place_entry_and_exits(adapter, bot: ScalpBot, symbol: str, side: str, price: float) -> dict[str, Any]:
    from app.brokers.models import OrderRequest, OrderSide, OrderType

    capital = float(bot.max_capital_usd)
    risk_pct = float(bot.risk_per_trade_pct) / 100.0
    notional = min(capital, capital * risk_pct * int(bot.leverage))
    if notional < 10:
        return {"error": f"Notional ${notional:.2f} demasiado pequeño (mín ~$10)"}
    qty = notional / price
    ccxt_sym = _ccxt_symbol(symbol)
    order_side = OrderSide.BUY if side == "long" else OrderSide.SELL
    pos_side = "LONG" if side == "long" else "SHORT"
    hedge = _is_hedge_mode(adapter, bot.user_id)
    meta: dict[str, Any] = {"leverage": int(bot.leverage), "source": "scalp_bot"}
    if hedge:
        meta["position_side"] = pos_side

    req = OrderRequest(
        symbol=ccxt_sym,
        side=order_side,
        order_type=OrderType.MARKET,
        quantity=Decimal(str(qty)),
        metadata=meta,
    )
    result = adapter.place_order(req)
    err_text = str(getattr(result, "error", "") or "")
    # -4061: we sent hedge positionSide on a one-way account (or vice versa)
    if (not getattr(result, "success", False)) and "-4061" in err_text:
        _hedge_cache[bot.user_id] = not hedge
        meta.pop("position_side", None)
        if not hedge:
            meta["position_side"] = pos_side
        req = OrderRequest(
            symbol=ccxt_sym,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(qty)),
            metadata=meta,
        )
        result = adapter.place_order(req)
        hedge = bool(meta.get("position_side"))
    if not getattr(result, "success", False) or not getattr(result, "order", None):
        return {"error": getattr(result, "error", None) or "Orden de entrada falló"}
    order = result.order
    fill_price = float(order.price or price)
    fill_qty = float(order.filled_quantity or qty)

    if side == "long":
        sl = fill_price * (1 - float(bot.sl_pct) / 100)
        tp = fill_price * (1 + float(bot.tp_pct) / 100)
        exit_side = "sell"
    else:
        sl = fill_price * (1 + float(bot.sl_pct) / 100)
        tp = fill_price * (1 - float(bot.tp_pct) / 100)
        exit_side = "buy"

    oco = {"success": False}
    try:
        oco = adapter.place_oco_order(
            ccxt_sym,
            exit_side,
            Decimal(str(fill_qty)),
            Decimal(str(tp)),
            Decimal(str(sl)),
        )
    except Exception as exc:
        oco = {"success": False, "error": str(exc)}

    if not oco.get("success"):
        # Fallback: separate reduce-only TP + SL
        exit_meta: dict[str, Any] = {"reduce_only": True, "source": "scalp_bot_tp"}
        if hedge:
            exit_meta["position_side"] = pos_side
        sl_meta = {**exit_meta, "source": "scalp_bot_sl"}
        try:
            adapter.place_order(OrderRequest(
                symbol=ccxt_sym,
                side=OrderSide.SELL if exit_side == "sell" else OrderSide.BUY,
                order_type=OrderType.TAKE_PROFIT,
                quantity=Decimal(str(fill_qty)),
                stop_price=Decimal(str(tp)),
                metadata=exit_meta,
            ))
            adapter.place_order(OrderRequest(
                symbol=ccxt_sym,
                side=OrderSide.SELL if exit_side == "sell" else OrderSide.BUY,
                order_type=OrderType.STOP,
                quantity=Decimal(str(fill_qty)),
                stop_price=Decimal(str(sl)),
                metadata=sl_meta,
            ))
            oco = {"success": True, "fallback": "separate_sl_tp"}
        except Exception as exc:
            oco = {"success": False, "error": str(exc)}

    return {
        "fill_price": fill_price,
        "fill_qty": fill_qty,
        "sl": sl,
        "tp": tp,
        "order_id": getattr(order, "broker_order_id", None),
        "oco": oco,
    }


def _record_db_position(bot: ScalpBot, symbol: str, side: str, fill: dict[str, Any]) -> None:
    from app.database.models.position import Position
    from app.database.models.trade import Trade

    db = SessionLocal()
    try:
        qty = Decimal(str(fill["fill_qty"]))
        px = Decimal(str(fill["fill_price"]))
        pos = Position(
            user_id=bot.user_id,
            broker_id=bot.broker_id,
            symbol=symbol if "/" in symbol else symbol.replace("USDT", "/USDT"),
            opened_at=datetime.now(tz=UTC),
            side="long" if side == "long" else "short",
            quantity=qty,
            entry_price=px,
            current_price=px,
            stop_loss=Decimal(str(fill["sl"])),
            take_profit=Decimal(str(fill["tp"])),
            status="open",
            strategy_name="scalp_bot",
            metadata_json={"source": "scalp_bot", "bot_id": bot.id, "leverage": bot.leverage, "position_side": side.upper()},
        )
        db.add(pos)
        db.flush()
        trade = Trade(
            user_id=bot.user_id,
            broker_id=bot.broker_id,
            timestamp=datetime.now(tz=UTC),
            symbol=pos.symbol,
            side="BUY" if side == "long" else "SELL",
            quantity=qty,
            price=px,
            commission=Decimal("0"),
            slippage=Decimal("0"),
            realized_pnl=Decimal("0"),
            strategy_name="scalp_bot",
            position_id=pos.id,
            metadata_json={"entry": True, "source": "scalp_bot", "bot_id": bot.id},
        )
        db.add(trade)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("scalp DB position save failed: %s", exc)
    finally:
        db.close()


def _maybe_close_open(session, bot: ScalpBot, adapter) -> None:
    if not bot.current_symbol or not bot.current_opened_at:
        return
    opened = bot.current_opened_at
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=UTC)
    held = datetime.now(tz=UTC) - opened
    if held < timedelta(minutes=int(bot.max_hold_minutes)):
        return
    # Time stop: market close
    try:
        from app.brokers.models import OrderRequest, OrderSide, OrderType
        side = bot.current_side or "long"
        qty = float(bot.current_qty or 0)
        if qty <= 0:
            return
        ccxt_sym = _ccxt_symbol(bot.current_symbol.replace("/", ""))
        close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
        close_meta: dict[str, Any] = {"reduce_only": True, "source": "scalp_bot_timestop"}
        if _is_hedge_mode(adapter, bot.user_id):
            close_meta["position_side"] = "LONG" if side == "long" else "SHORT"
        adapter.place_order(OrderRequest(
            symbol=ccxt_sym,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(qty)),
            metadata=close_meta,
        ))
        _log(session, bot.id, "sell" if side == "long" else "buy", f"Time-stop {bot.current_symbol} a {int(bot.max_hold_minutes)}m",
             level="warn", symbol=bot.current_symbol, side=side)
        bot.current_symbol = None
        bot.current_side = None
        bot.current_qty = None
        bot.current_entry = None
        bot.current_opened_at = None
        bot.current_sl = None
        bot.current_tp = None
        bot.trades_count = (bot.trades_count or 0) + 1
    except Exception as exc:
        _log(session, bot.id, "error", f"Time-stop falló: {exc}", level="error")


def _reset_daily_if_needed(bot: ScalpBot) -> None:
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    if bot.daily_pnl_date != today:
        bot.daily_pnl = Decimal("0")
        bot.daily_pnl_date = today


class ScalpEngine:
    def __init__(self, bot: ScalpBot, session=None) -> None:
        self._bot = bot
        self._session = session

    def run_cycle(self) -> dict[str, Any]:
        bot = self._bot
        session = self._session
        own_session = False
        if session is None:
            session = SessionLocal()
            own_session = True
            bot = session.query(ScalpBot).filter_by(id=bot.id).first()
            if not bot:
                if own_session:
                    session.close()
                return {"error": "bot missing"}

        try:
            return self._run(session, bot)
        finally:
            if own_session:
                session.commit()
                session.close()

    def _run(self, session, bot: ScalpBot) -> dict[str, Any]:
        bot.last_run_at = datetime.now(tz=UTC)
        _reset_daily_if_needed(bot)

        if heartbeat_expired(bot.last_heartbeat_at):
            if bot.is_active:
                bot.is_active = False
                bot.status = "stopped"
                _log(session, bot.id, "heartbeat_timeout", "Desktop desconectado — se detienen nuevas entradas (SL/TP siguen en el broker)", level="warn")
            return {"stopped": "heartbeat"}

        if float(bot.daily_pnl or 0) <= -float(bot.max_daily_loss_usd):
            bot.is_active = False
            bot.status = "killed"
            _log(session, bot.id, "killed", f"Pérdida diaria ${float(bot.daily_pnl):.2f} alcanzó el límite", level="error")
            return {"killed": True}

        adapter = _get_futures_adapter(bot)
        if adapter is None:
            _log(session, bot.id, "error", "Sin credenciales de broker / no se pudo abrir futuros", level="error")
            bot.status = "error"
            return {"error": "no_adapter"}

        _maybe_close_open(session, bot, adapter)

        if bot.current_symbol:
            return {"holding": bot.current_symbol}

        ranked = _rank_universe(float(bot.min_atr_pct))
        if not ranked:
            _log(session, bot.id, "scan", "Sin candidatos con ATR suficiente")
            return {"scan": 0}

        top3 = ranked[:3]
        summary = ", ".join(f"{s['symbol']} atr={s['atr_pct']} vol={s['vol_ratio']}x" for s in top3)
        state = bot.state_json or {}
        last_scan = state.get("last_scan_msg")
        last_scan_ts = float(state.get("last_scan_ts") or 0)
        if summary != last_scan or (time.time() - last_scan_ts) > 60:
            _log(session, bot.id, "scan", f"Top volatilidad: {summary}")
            state["last_scan_msg"] = summary
            state["last_scan_ts"] = time.time()
            bot.state_json = dict(state)

        preferred_side = "long" if top3[0]["return_5m"] >= 0 else "short"
        pick_sym = top3[0]["symbol"]
        if bot.use_ai_filter:
            ai = _ai_filter(bot, top3)
            if ai and ai["side"] != "skip" and ai["pick"]:
                for s in top3:
                    if s["symbol"] == ai["pick"] or s["symbol"].replace("USDT", "") == ai["pick"].replace("USDT", ""):
                        pick_sym = s["symbol"]
                        break
                preferred_side = ai["side"]
                ai_msg = f"IA eligió {pick_sym} {preferred_side} conf={ai.get('conf')}"
            else:
                ai_msg = f"IA skip/fallback → {pick_sym} {preferred_side}"
            state = bot.state_json or {}
            if state.get("last_ai_msg") != ai_msg:
                _log(session, bot.id, "ai_pick", ai_msg, symbol=pick_sym, side=preferred_side)
                state["last_ai_msg"] = ai_msg
                bot.state_json = dict(state)

        candidate = next((s for s in ranked if s["symbol"] == pick_sym), top3[0])
        ok, reason = _entry_signal(candidate, preferred_side)
        if not ok:
            skip_key = f"{candidate['symbol']}:{preferred_side}:{reason[:80]}"
            state = bot.state_json or {}
            last_skip = state.get("last_skip")
            last_skip_ts = float(state.get("last_skip_ts") or 0)
            if skip_key != last_skip or (time.time() - last_skip_ts) > 30:
                _log(session, bot.id, "skip", f"{candidate['symbol']} {preferred_side}: {reason}", symbol=candidate["symbol"], side=preferred_side)
                state["last_skip"] = skip_key
                state["last_skip_ts"] = time.time()
                bot.state_json = dict(state)
            return {"skipped": candidate["symbol"]}

        fill = _place_entry_and_exits(adapter, bot, candidate["symbol"], preferred_side, candidate["price"])
        if fill.get("error"):
            _log(session, bot.id, "error", f"Entrada falló: {fill['error']}", level="error", symbol=candidate["symbol"])
            return {"error": fill["error"]}

        bot.current_symbol = candidate["symbol"]
        bot.current_side = preferred_side
        bot.current_qty = Decimal(str(fill["fill_qty"]))
        bot.current_entry = Decimal(str(fill["fill_price"]))
        bot.current_opened_at = datetime.now(tz=UTC)
        bot.current_sl = Decimal(str(fill["sl"]))
        bot.current_tp = Decimal(str(fill["tp"]))
        event = "buy" if preferred_side == "long" else "sell"
        _log(
            session, bot.id, event,
            f"{preferred_side.upper()} {candidate['symbol']} @ {fill['fill_price']:.6f} qty={fill['fill_qty']:.6f} SL={fill['sl']:.6f} TP={fill['tp']:.6f}",
            symbol=candidate["symbol"], side=preferred_side, price=fill["fill_price"], quantity=fill["fill_qty"],
        )
        try:
            _record_db_position(bot, candidate["symbol"], preferred_side, fill)
        except Exception as exc:
            logger.warning("scalp position persist: %s", exc)
        return {"entered": candidate["symbol"], "side": preferred_side, "fill": fill}
