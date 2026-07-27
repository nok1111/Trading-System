"""Scheduler de paper trading persistente (FASE 5)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event, Lock, Thread
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.brokers.broker import Broker
from app.config import Settings
from app.data.market_data_service import MarketDataService
from app.database.models.account_snapshot import AccountSnapshot
from app.database.models.position import Position
from app.database.models.prediction_record import PredictionRecord
from app.database.models.strategy_run import StrategyRun
from app.execution.execution_engine import ExecutionEngine
from app.risk.risk_manager import RiskManager
from app.strategies.strategy import Strategy


class PaperTradingScheduler:
    """Ejecuta la estrategia periódicamente en modo paper."""

    def __init__(
        self,
        settings: Settings,
        strategy: Strategy,
        data_service: MarketDataService,
        broker: Broker,
        risk_manager: RiskManager,
        session_factory: Callable[[], Session],
    ) -> None:
        self.settings = settings
        self.strategy = strategy
        self.data_service = data_service
        self.broker = broker
        self.risk_manager = risk_manager
        self.session_factory = session_factory
        self._strategy_run_id: int | None = None
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self._hold_counts: dict[str, int] = {}
        self._interval: int = settings.PAPER_TRADING_INTERVAL_SECONDS
        self._active_symbols: set[str] = set()
        self._tick_count: int = 0
        self._bar_cache: dict[str, pd.DataFrame] = {}
        self._bar_cache_time: dict[str, float] = {}
        self._last_trade_time: dict[str, float] = {}
        self._trade_cooldown_seconds: float = 30.0

    @property
    def is_running(self) -> bool:
        """Indica si el scheduler sigue ejecutándose."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> StrategyRun:
        """Inicia la ejecución periódica en segundo plano."""
        if not self.settings.PAPER_TRADING_ENABLED:
            raise RuntimeError("PAPER_TRADING_ENABLED no está activado")

        with self._lock:
            session = self.session_factory()
            try:
                run = StrategyRun(
                    strategy_name=self.strategy.name,
                    mode="paper",
                    status="running",
                    config=self.settings.to_safe_dict(),
                )
                session.add(run)
                session.commit()
                self._strategy_run_id = run.id
            finally:
                session.close()

            self._stop_event.clear()
            self._thread = Thread(target=self._run_loop, daemon=True)
            self._thread.start()

        return run

    def stop(self) -> None:
        """Detiene el scheduler y marca la ejecución como stopped."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._lock:
            session = self.session_factory()
            try:
                self._finalize_run(session)
                session.commit()
            finally:
                session.close()

    def tick(self, session: Session | None = None) -> dict[str, Any]:
        """Ejecuta un ciclo manual. Útil para tests."""
        close_session = session is None
        session = session or self.session_factory()
        try:
            result = self._tick(session)
            if close_session:
                session.commit()
            if close_session and self.strategy.name == "MLStrategy":
                self._evaluate_past_predictions_external()
            return result
        except Exception:
            if close_session:
                session.rollback()
                self._set_run_status(session, "error")
                session.commit()
            raise
        finally:
            if close_session:
                session.close()

    def _run_loop(self) -> None:
        import logging
        while not self._stop_event.is_set():
            local_time = self.settings.now_local().strftime("%Y-%m-%d %H:%M:%S %Z")
            logging.info(f"PaperTrading tick started at {local_time}")
            try:
                self.tick()
            except Exception as e:
                logging.error(f"PaperTrading tick error: {e}", exc_info=True)
                self._set_run_status_external("error")
                break
            self._stop_event.wait(self._interval)

    def set_interval(self, seconds: int) -> None:
        """Update the tick interval at runtime (min 5s)."""
        if seconds >= 5:
            self._interval = seconds

    def _set_run_status_external(self, status: str) -> None:
        with self._lock:
            session = self.session_factory()
            try:
                self._set_run_status(session, status)
                session.commit()
            finally:
                session.close()

    def _set_run_status(self, session: Session, status: str) -> None:
        if self._strategy_run_id is None:
            return
        run = session.get(StrategyRun, self._strategy_run_id)
        if run is not None:
            run.status = status
            run.ended_at = datetime.now(UTC)

    def _finalize_run(self, session: Session) -> None:
        self._set_run_status(session, "stopped")

    def _should_refresh_bars(self, symbol: str, timeframe: str) -> bool:
        """Check if cached bars are stale based on timeframe interval."""
        import time as _time
        last = self._bar_cache_time.get(symbol, 0)
        tf_seconds = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
                      "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400}
        interval = tf_seconds.get(timeframe, 300)
        return (_time.time() - last) >= interval * 0.9

    def _get_bars(self, symbol: str, start, end, timeframe: str) -> pd.DataFrame | None:
        """Get bars from cache or download if stale."""
        import time as _time
        import logging
        if symbol in self._bar_cache and not self._should_refresh_bars(symbol, timeframe):
            return self._bar_cache[symbol]
        try:
            df = self.data_service.get_historical_bars(symbol, start, end, timeframe)
            if len(df) >= self.strategy.min_bars:
                self._bar_cache[symbol] = df
                self._bar_cache_time[symbol] = _time.time()
                return df
        except Exception as e:
            logging.warning(f"Failed to download data for {symbol}: {e}")
            if symbol in self._bar_cache:
                return self._bar_cache[symbol]
        return None

    def _is_in_cooldown(self, symbol: str) -> bool:
        """Check if symbol is in trade cooldown to prevent over-trading."""
        import time as _time
        last = self._last_trade_time.get(symbol, 0)
        return (_time.time() - last) < self._trade_cooldown_seconds

    def _tick(self, session: Session) -> dict[str, Any]:
        import logging
        import time as _time
        engine = ExecutionEngine(self.broker, self.risk_manager, session, self.settings)
        all_symbols = self.settings.symbols_list
        end = datetime.now(UTC).date()
        start = end - timedelta(days=self.settings.PAPER_TRADING_LOOKBACK_DAYS)
        timeframe = self.settings.DATA_TIMEFRAME

        is_ml = self.strategy.name == "MLStrategy"
        self._tick_count += 1

        # Every 4 ticks, fetch top gainers from Binance and add them to the symbol pool
        if self._tick_count % 4 == 0:
            try:
                from app.data.binance_source import BinanceDataSource
                ds = BinanceDataSource()
                movers = ds.get_top_movers(market="spot", limit=10, quote="USDT")
                mover_symbols = [m["symbol"] for m in movers.get("gainers", [])]
                for ms in mover_symbols:
                    if ms not in all_symbols:
                        all_symbols.append(ms)
                logging.info(f"Top gainers fetched: {mover_symbols[:5]}")
            except Exception as e:
                logging.warning(f"Failed to fetch top movers: {e}")

        open_positions = self._get_all_open_positions(session)
        open_symbols = {p.symbol for p in open_positions}
        position_map = {p.symbol: p for p in open_positions}
        stale_symbols = self._get_stale_symbols()
        candidate_symbols = [s for s in all_symbols if s not in stale_symbols]
        symbols = list(open_symbols) + [s for s in candidate_symbols if s not in open_symbols]
        symbols = symbols[: self.settings.MAX_ACTIVE_SYMBOLS]

        # Subscribe new symbols to the price stream for real-time prices
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream:
                for sym in symbols:
                    if not stream.get_price(sym):
                        stream.add_symbol(sym)
        except Exception:
            pass

        # Only download bars for symbols not in cache or with stale cache
        market_data: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            df = self._get_bars(symbol, start, end, timeframe)
            if df is not None:
                market_data[symbol] = df

        hold_symbols_this_tick: set[str] = set()

        for symbol, df in market_data.items():
            df_price = Decimal(str(df.iloc[-1]["close"]))
            current_price = self._get_live_price(symbol) or df_price
            if hasattr(self.broker, 'set_price'):
                self.broker.set_price(symbol, current_price)
            has_position = symbol in open_symbols
            entry_price = self._entry_price(session, symbol) if has_position else None
            bars_in_pos = self._calculate_bars_in_position(position_map.get(symbol), timeframe) if has_position else 0
            highest_price = None
            if has_position:
                pos = position_map.get(symbol)
                if pos is not None:
                    meta = pos.metadata_json or {}
                    stored_high = meta.get("highest_price")
                    if stored_high is not None:
                        highest_price = Decimal(str(stored_high))
                    if highest_price is None or current_price > highest_price:
                        highest_price = current_price
                        meta["highest_price"] = str(highest_price)
                        pos.metadata_json = meta
                        session.add(pos)
                        session.flush()
            signal = self.strategy.generate_signal(
                symbol,
                df,
                current_price=current_price,
                has_position=has_position,
                position_entry_price=entry_price,
                bars_in_position=bars_in_pos,
                position_highest_price=highest_price,
            )
            if is_ml:
                self._save_prediction(session, symbol, signal, current_price)
            if signal.signal_type == "HOLD":
                hold_symbols_this_tick.add(symbol)
            elif signal.signal_type != "HOLD":
                # Skip SELL signals for held positions (user manually set hold)
                if signal.signal_type == "SELL" and has_position:
                    pos_meta = position_map.get(symbol)
                    if pos_meta and (pos_meta.metadata_json or {}).get("hold"):
                        hold_symbols_this_tick.add(symbol)
                        continue
                # Enforce cooldown for BUY signals (not for SELL — we always want to allow exits)
                if signal.signal_type == "BUY" and self._is_in_cooldown(symbol):
                    hold_symbols_this_tick.add(symbol)
                    continue
                try:
                    result = engine.process_signal(signal)
                    if result is not None:
                        self._last_trade_time[symbol] = _time.time()
                        logging.info(f"Orden ejecutada: {result.side} {result.symbol} x{result.filled_quantity} @ {result.price}")
                    else:
                        logging.info(f"Señal {signal.signal_type} {symbol} rechazada por risk manager")
                    session.flush()
                except Exception as e:
                    logging.warning(f"process_signal error for {symbol}: {e}")
                    session.rollback()

        # Update hold counts
        self._update_hold_counts(hold_symbols_this_tick, open_symbols)

        # If too many symbols in HOLD, sell the one with least loss to free space
        self._enforce_max_hold_symbols(session, engine, open_positions)

        account = self.broker.get_account()
        snapshot = AccountSnapshot(
            timestamp=datetime.now(UTC),
            cash=account.cash,
            equity=account.equity,
            buying_power=account.buying_power,
            margin_used=account.margin_used,
            daily_pnl=account.daily_pnl,
            total_pnl=account.total_pnl,
            open_positions_count=account.open_positions_count,
            strategy_run_id=self._strategy_run_id,
        )
        session.add(snapshot)

        return {
            "status": "ok",
            "symbols": symbols,
            "timestamp": snapshot.timestamp.isoformat(),
            "local_time": self.settings.now_local().strftime("%Y-%m-%d %H:%M:%S %Z"),
        }

    def _evaluate_past_predictions_external(self) -> None:
        """Evalua predicciones pasadas en una sesion independiente."""
        import logging
        session = self.session_factory()
        try:
            self._evaluate_past_predictions(session, self.settings.symbols_list)
            session.commit()
        except Exception as e:
            logging.error(f"Error evaluating past predictions: {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()

    def _save_prediction(self, session: Session, symbol: str, signal: Any, current_price: Decimal) -> None:
        """Guarda cada prediccion ML en la DB para feedback posterior."""
        proba = signal.metadata_json.get("ml_probability", 0) if signal.metadata_json else 0
        record = PredictionRecord(
            timestamp=datetime.now(UTC),
            symbol=symbol,
            signal_type=signal.signal_type,
            probability=Decimal(str(proba)),
            price_at_prediction=current_price,
            forward_window=5,
            strategy_run_id=self._strategy_run_id,
            metadata_json=signal.metadata_json or {},
        )
        session.add(record)

    def _evaluate_past_predictions(self, session: Session, symbols: list[str]) -> None:
        """Evalua predicciones pasadas comparando el precio actual vs el de prediccion."""
        now = datetime.now(UTC)
        pending = (
            session.query(PredictionRecord)
            .filter(PredictionRecord.evaluated == False)  # noqa: E712
            .filter(PredictionRecord.signal_type != "HOLD")
            .all()
        )
        for rec in pending:
            rec_ts = rec.timestamp.replace(tzinfo=UTC) if rec.timestamp.tzinfo is None else rec.timestamp
            age_minutes = (now - rec_ts).total_seconds() / 60
            if age_minutes < rec.forward_window:
                continue
            end = now.date()
            start = end - timedelta(days=self.settings.PAPER_TRADING_LOOKBACK_DAYS)
            try:
                df = self.data_service.get_historical_bars(rec.symbol, start, end, self.settings.DATA_TIMEFRAME)
                if len(df) < 2:
                    continue
                price_now = Decimal(str(df.iloc[-1]["close"]))
                price_then = rec.price_at_prediction
                actual_up = price_now > price_then
                actual_direction = "UP" if actual_up else "DOWN"
                predicted_up = rec.signal_type == "BUY"
                correct = (actual_up == predicted_up)
                rec.evaluated = True
                rec.actual_direction = actual_direction
                rec.correct = correct
                rec.price_at_evaluation = price_now
                rec.evaluated_at = now
            except Exception as e:
                import logging
                logging.warning(f"Error evaluating prediction {rec.id}: {e}")
                continue

    def _calculate_bars_in_position(self, position: Position | None, timeframe: str) -> int:
        """Estima cuántas barras han pasado desde que se abrió la posición."""
        if position is None or position.opened_at is None:
            return 0
        now = datetime.now(UTC)
        opened = position.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=UTC)
        elapsed_seconds = (now - opened).total_seconds()
        tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
        minutes = tf_minutes.get(timeframe, 5)
        return max(1, int(elapsed_seconds / (minutes * 60)))

    def _has_open_position(self, session: Session, symbol: str) -> bool:
        return (
            session.query(Position)
            .filter_by(symbol=symbol, status="open")
            .first()
            is not None
        )

    def _entry_price(self, session: Session, symbol: str) -> Decimal | None:
        position = session.query(Position).filter_by(symbol=symbol, status="open").first()
        return position.entry_price if position is not None else None

    def _get_all_open_positions(self, session: Session) -> list[Position]:
        return session.query(Position).filter_by(status="open").all()

    def _get_live_price(self, symbol: str) -> Decimal | None:
        """Get real-time price from WebSocket if available."""
        try:
            from app.data.price_stream import get_price_stream
            stream = get_price_stream()
            if stream and stream.is_connected:
                price = stream.get_price(symbol)
                if price and price > 0:
                    return price
        except Exception:
            pass
        return None

    def _get_stale_symbols(self) -> set[str]:
        """Symbols that have been in HOLD for too many consecutive ticks."""
        stale_threshold = self.settings.HOLD_STALE_TICKS
        return {
            sym for sym, count in self._hold_counts.items()
            if count >= stale_threshold and sym not in self._active_symbols
        }

    def _update_hold_counts(self, hold_symbols: set[str], open_symbols: set[str]) -> None:
        """Track consecutive HOLD ticks per symbol. Reset on non-HOLD or when position opens."""
        for sym in hold_symbols:
            self._hold_counts[sym] = self._hold_counts.get(sym, 0) + 1
        # Reset count for symbols that generated a signal or have an open position
        all_symbols = self.settings.symbols_list
        for sym in all_symbols:
            if sym not in hold_symbols:
                self._hold_counts.pop(sym, None)
        # Track active symbols (open positions)
        self._active_symbols = open_symbols

    def _enforce_max_hold_symbols(
        self,
        session: Session,
        engine: ExecutionEngine,
        open_positions: list[Position],
    ) -> None:
        """If more than MAX_HOLD_SYMBOLS positions are open, sell the one with least loss."""
        import logging
        max_hold = self.settings.MAX_HOLD_SYMBOLS
        # Filter out held positions (user set hold to prevent auto-sell)
        sellable = [p for p in open_positions if not (p.metadata_json or {}).get("hold")]
        if len(sellable) <= max_hold:
            return
        sorted_positions = sorted(sellable, key=lambda p: p.unrealized_pnl, reverse=True)
        excess = len(sellable) - max_hold
        for pos in sorted_positions[:excess]:
            try:
                from app.models.signal import SignalCreate
                sell_signal = SignalCreate(
                    timestamp=datetime.now(UTC),
                    symbol=pos.symbol,
                    signal_type="SELL",
                    confidence=Decimal("1.0"),
                    entry_price=pos.current_price or pos.entry_price,
                    strategy_name=self.strategy.name,
                    explanation="Auto-sell: max hold symbols exceeded",
                )
                engine.process_signal(sell_signal)
                session.flush()
                logging.info(f"Auto-sold {pos.symbol} to free space (unrealized PnL: {pos.unrealized_pnl})")
            except Exception as e:
                logging.warning(f"Auto-sell failed for {pos.symbol}: {e}")
                session.rollback()

    def manual_sell(self, symbol: str) -> dict[str, Any]:
        """Manually close a position by symbol. Called from API endpoint."""
        import logging
        session = self.session_factory()
        try:
            position = session.query(Position).filter_by(symbol=symbol, status="open").first()
            if position is None:
                return {"status": "no_position", "symbol": symbol}
            engine = ExecutionEngine(self.broker, self.risk_manager, session, self.settings)
            from app.models.signal import SignalCreate
            sell_signal = SignalCreate(
                timestamp=datetime.now(UTC),
                symbol=symbol,
                signal_type="SELL",
                confidence=Decimal("1.0"),
                entry_price=position.current_price or position.entry_price,
                strategy_name=self.strategy.name,
                explanation="Manual sell",
            )
            engine.process_signal(sell_signal)
            session.commit()
            return {"status": "sold", "symbol": symbol, "entry_price": str(position.entry_price)}
        except Exception as e:
            session.rollback()
            logging.error(f"Manual sell error for {symbol}: {e}")
            return {"status": "error", "symbol": symbol, "error": str(e)}
        finally:
            session.close()
