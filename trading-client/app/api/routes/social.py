"""Social trading endpoints — leaders, signals, follow, copy.

Modelo B: Signal Feed + Copy Manual
- Los líderes publican señales (buy/sell con SL/TP)
- Los seguidores ven un feed y copian manualmente
- Cross-broker: el seguidor puede usar cualquier broker conectado
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.models.social_follow import SocialCopyTrade, SocialFollow
from app.database.models.social_leader import SocialLeader
from app.database.models.social_signal import SocialSignal
from app.database.session import get_db
from app.services.auth import LocalUser, get_current_user, get_optional_user
from app.services.signal_normalizer import (
    calculate_copy_size,
    calculate_quantity,
    check_slippage,
    normalize_symbol,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/social", tags=["social"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterLeaderRequest(BaseModel):
    display_name: str
    bio: str = ""
    broker_id: str = "binance"
    is_public: bool = True


class PublishSignalRequest(BaseModel):
    symbol: str
    side: str  # BUY, SELL, CLOSE
    size_pct: float = 5.0
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""


class FollowRequest(BaseModel):
    leader_id: int
    auto_copy: bool = False
    copy_pct: float = 100.0
    max_positions: int = 10
    symbol_filter: str = ""
    max_drawdown_pct: float = 20.0


class CopySignalRequest(BaseModel):
    broker_id: str  # broker del follower (de los que tiene conectados)
    size_usd: float | None = None  # opcional, si no se usa copy_pct del follow


class UpdateFollowRequest(BaseModel):
    auto_copy: bool | None = None
    copy_pct: float | None = None
    max_positions: int | None = None
    symbol_filter: str | None = None
    max_drawdown_pct: float | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# Leader endpoints
# ---------------------------------------------------------------------------

@router.post("/leader/register")
def register_leader(
    req: RegisterLeaderRequest,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Convertirse en líder — crea o actualiza el perfil de líder."""
    existing = db.execute(
        select(SocialLeader).where(SocialLeader.user_id == user.id)
    ).scalar_one_or_none()

    if existing:
        existing.display_name = req.display_name
        existing.bio = req.bio
        existing.broker_id = req.broker_id
        existing.is_public = req.is_public
        db.commit()
        db.refresh(existing)
        return _leader_dict(existing)

    leader = SocialLeader(
        user_id=user.id,
        display_name=req.display_name,
        bio=req.bio,
        broker_id=req.broker_id,
        is_public=req.is_public,
    )
    db.add(leader)
    db.commit()
    db.refresh(leader)
    return _leader_dict(leader)


@router.get("/leaders")
def list_leaders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("roi_30d", pattern="^(roi_30d|roi_90d|roi_all|win_rate|total_followers|total_trades)$"),
) -> list[dict]:
    """Listar líderes públicos ordenados por performance."""
    stmt = (
        select(SocialLeader)
        .where(SocialLeader.is_public == True)  # noqa: E712
        .order_by(desc(getattr(SocialLeader, sort)))
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return [_leader_dict(r, include_stats=True) for r in rows]


@router.get("/leaders/{leader_id}")
def get_leader(
    leader_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Perfil detallado de un líder."""
    leader = db.execute(
        select(SocialLeader).where(SocialLeader.id == leader_id)
    ).scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Líder no encontrado")
    return _leader_dict(leader, include_stats=True)


@router.get("/leaders/{leader_id}/signals")
def get_leader_signals(
    leader_id: int,
    db: Annotated[Session, Depends(get_db)],
    status: str = Query("all", pattern="^(all|active|closed)$"),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Historial de señales de un líder."""
    stmt = select(SocialSignal).where(SocialSignal.leader_id == leader_id)
    if status == "active":
        stmt = stmt.where(SocialSignal.status == "active")
    elif status == "closed":
        stmt = stmt.where(SocialSignal.status.in_(["closed", "cancelled"]))
    stmt = stmt.order_by(desc(SocialSignal.created_at)).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [_signal_dict(s) for s in rows]


# ---------------------------------------------------------------------------
# Signal endpoints
# ---------------------------------------------------------------------------

@router.post("/signals")
def publish_signal(
    req: PublishSignalRequest,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Publicar una nueva señal (solo líderes)."""
    leader = db.execute(
        select(SocialLeader).where(SocialLeader.user_id == user.id)
    ).scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=403, detail="No eres líder. Regístrate primero con /api/social/leader/register")

    if req.side not in ("BUY", "SELL", "CLOSE"):
        raise HTTPException(status_code=400, detail="side debe ser BUY, SELL o CLOSE")

    signal = SocialSignal(
        leader_id=leader.id,
        user_id=user.id,
        symbol=req.symbol.upper().replace("/", "").replace("-", "").replace("_", ""),
        side=req.side,
        size_pct=req.size_pct,
        entry_price=Decimal(str(req.entry_price)) if req.entry_price else None,
        stop_loss=Decimal(str(req.stop_loss)) if req.stop_loss else None,
        take_profit=Decimal(str(req.take_profit)) if req.take_profit else None,
        broker_id=leader.broker_id,
        status="active",
        comment=req.comment,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    # Broadcast via WebSocket (best-effort)
    _broadcast_signal(signal, leader)

    return _signal_dict(signal)


@router.get("/signals/feed")
def signals_feed(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[LocalUser | None, Depends(get_optional_user)] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query("active", pattern="^(active|all|closed)$"),
) -> dict:
    """Feed de señales recientes (paginado)."""
    stmt = select(SocialSignal)
    if status == "active":
        stmt = stmt.where(SocialSignal.status == "active")
    elif status == "closed":
        stmt = stmt.where(SocialSignal.status.in_(["closed", "cancelled"]))

    # Join con leaders para solo mostrar señales de líderes públicos
    stmt = stmt.join(SocialLeader, SocialSignal.leader_id == SocialLeader.id).where(
        SocialLeader.is_public == True  # noqa: E712
    )
    stmt = stmt.order_by(desc(SocialSignal.created_at)).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()

    # Get leader info for each signal
    leader_ids = {s.leader_id for s in rows}
    leaders = {}
    if leader_ids:
        leader_rows = db.execute(
            select(SocialLeader).where(SocialLeader.id.in_(leader_ids))
        ).scalars().all()
        leaders = {l.id: l for l in leader_rows}

    signals = []
    for s in rows:
        d = _signal_dict(s)
        leader = leaders.get(s.leader_id)
        if leader:
            d["leader"] = {
                "id": leader.id,
                "display_name": leader.display_name,
                "broker_id": leader.broker_id,
                "roi_30d": leader.roi_30d,
                "win_rate": leader.win_rate,
                "total_followers": leader.total_followers,
            }
        signals.append(d)

    return {"signals": signals, "count": len(signals), "offset": offset}


@router.post("/signals/{signal_id}/close")
def close_signal(
    signal_id: int,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    close_price: float | None = None,
) -> dict:
    """Cerrar una señal (solo el líder que la publicó)."""
    signal = db.execute(
        select(SocialSignal).where(SocialSignal.id == signal_id)
    ).scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Señal no encontrada")
    if signal.user_id != user.id:
        raise HTTPException(status_code=403, detail="Solo el líder puede cerrar esta señal")

    signal.status = "closed"
    signal.closed_at = datetime.utcnow()
    if close_price:
        signal.close_price = Decimal(str(close_price))
        if signal.entry_price and signal.entry_price > 0:
            signal.pnl_pct = round(
                (float(signal.close_price) - float(signal.entry_price)) / float(signal.entry_price) * 100, 2
            )
    db.commit()
    db.refresh(signal)
    return _signal_dict(signal)


# ---------------------------------------------------------------------------
# Follow / Copy endpoints
# ---------------------------------------------------------------------------

@router.post("/follow")
def follow_leader(
    req: FollowRequest,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Seguir a un líder (con configuración de copy)."""
    leader = db.execute(
        select(SocialLeader).where(SocialLeader.id == req.leader_id)
    ).scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Líder no encontrado")

    # Check if already following
    existing = db.execute(
        select(SocialFollow).where(
            SocialFollow.follower_id == user.id,
            SocialFollow.leader_id == req.leader_id,
            SocialFollow.active == True,  # noqa: E712
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Ya sigues a este líder")

    follow = SocialFollow(
        follower_id=user.id,
        leader_id=req.leader_id,
        auto_copy=req.auto_copy,
        copy_pct=req.copy_pct,
        max_positions=req.max_positions,
        symbol_filter=req.symbol_filter,
        max_drawdown_pct=req.max_drawdown_pct,
    )
    db.add(follow)

    # Update follower count on leader
    leader.total_followers = (leader.total_followers or 0) + 1
    db.commit()
    db.refresh(follow)
    return _follow_dict(follow)


@router.delete("/follow/{follow_id}")
def unfollow_leader(
    follow_id: int,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Dejar de seguir a un líder."""
    follow = db.execute(
        select(SocialFollow).where(SocialFollow.id == follow_id)
    ).scalar_one_or_none()
    if not follow:
        raise HTTPException(status_code=404, detail="Follow no encontrado")
    if follow.follower_id != user.id:
        raise HTTPException(status_code=403, detail="No es tu follow")

    follow.active = False
    # Decrement follower count
    leader = db.execute(
        select(SocialLeader).where(SocialLeader.id == follow.leader_id)
    ).scalar_one_or_none()
    if leader and leader.total_followers > 0:
        leader.total_followers -= 1
    db.commit()
    return {"ok": True}


@router.patch("/follow/{follow_id}")
def update_follow(
    follow_id: int,
    req: UpdateFollowRequest,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Actualizar configuración de un follow."""
    follow = db.execute(
        select(SocialFollow).where(SocialFollow.id == follow_id)
    ).scalar_one_or_none()
    if not follow:
        raise HTTPException(status_code=404, detail="Follow no encontrado")
    if follow.follower_id != user.id:
        raise HTTPException(status_code=403, detail="No es tu follow")

    if req.auto_copy is not None:
        follow.auto_copy = req.auto_copy
    if req.copy_pct is not None:
        follow.copy_pct = req.copy_pct
    if req.max_positions is not None:
        follow.max_positions = req.max_positions
    if req.symbol_filter is not None:
        follow.symbol_filter = req.symbol_filter
    if req.max_drawdown_pct is not None:
        follow.max_drawdown_pct = req.max_drawdown_pct
    if req.active is not None:
        follow.active = req.active
    db.commit()
    db.refresh(follow)
    return _follow_dict(follow)


@router.get("/my-follows")
def my_follows(
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """Listar mis follows activos."""
    rows = db.execute(
        select(SocialFollow).where(
            SocialFollow.follower_id == user.id,
            SocialFollow.active == True,  # noqa: E712
        )
    ).scalars().all()
    return [_follow_dict(f) for f in rows]


# ---------------------------------------------------------------------------
# Copy signal — ejecutar trade en el broker del follower
# ---------------------------------------------------------------------------

@router.post("/signals/{signal_id}/copy")
def copy_signal(
    signal_id: int,
    req: CopySignalRequest,
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Copiar una señal manualmente — ejecuta un trade en el broker del follower.

    El follower especifica qué broker usar (de los que tiene conectados).
    El sistema normaliza el símbolo al formato del broker destino.
    """
    from app.brokers.models import BrokerCredentials
    from app.brokers.registry import get_adapter
    from app.services.broker_account_service import list_accounts
    from app.crypto.utils import decrypt

    signal = db.execute(
        select(SocialSignal).where(SocialSignal.id == signal_id)
    ).scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Señal no encontrada")
    if signal.status != "active":
        raise HTTPException(status_code=400, detail="Esta señal ya no está activa")

    # Get follower's broker account
    accounts = list_accounts(db, user.id)
    broker_account = next((a for a in accounts if a.get("broker_id") == req.broker_id), None)
    if not broker_account:
        raise HTTPException(
            status_code=400,
            detail=f"No tienes el broker '{req.broker_id}' conectado. Brokers disponibles: {', '.join(a.get('broker_id', '?') for a in accounts)}"
        )

    # Decrypt credentials
    try:
        creds = BrokerCredentials(
            broker_id=broker_account["broker_id"],
            api_key=decrypt(broker_account["api_key_enc"]),
            api_secret=decrypt(broker_account["api_secret_enc"]),
            passphrase=decrypt(broker_account["passphrase_enc"]) if broker_account.get("passphrase_enc") else None,
            testnet=broker_account.get("environment") == "testnet",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al desencriptar credenciales: {exc}") from exc

    # Normalize symbol for target broker
    target_symbol = normalize_symbol(signal.symbol, req.broker_id)

    # Get current price from broker
    adapter = get_adapter(req.broker_id, creds)
    try:
        ticker = adapter.get_ticker(target_symbol)
        current_price = Decimal(str(ticker.last_price))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error al obtener precio de {target_symbol}: {exc}") from exc

    # Check slippage
    if not check_slippage(signal.entry_price, current_price, max_slippage_pct=5.0):
        raise HTTPException(
            status_code=400,
            detail=f"Slippage demasiado alto. Precio señal: {signal.entry_price}, precio actual: {current_price}"
        )

    # Calculate position size
    if req.size_usd and req.size_usd > 0:
        size_usd = Decimal(str(req.size_usd))
    else:
        # Use copy_pct from follow config
        follow = db.execute(
            select(SocialFollow).where(
                SocialFollow.follower_id == user.id,
                SocialFollow.leader_id == signal.leader_id,
                SocialFollow.active == True,  # noqa: E712
            )
        ).scalar_one_or_none()
        copy_pct = follow.copy_pct if follow else 100.0

        # Get follower's portfolio value
        try:
            portfolio = adapter.get_portfolio()
            follower_portfolio = Decimal(str(portfolio.total_usd))
        except Exception:
            follower_portfolio = Decimal("1000")  # fallback

        size_usd = calculate_copy_size(
            leader_size_pct=signal.size_pct,
            leader_portfolio_usd=10000,  # estimate
            follower_portfolio_usd=float(follower_portfolio),
            copy_pct=copy_pct,
        )

    if size_usd <= 0:
        raise HTTPException(status_code=400, detail="Tamaño de posición inválido")

    quantity = calculate_quantity(size_usd, current_price)
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Cantidad calculada inválida")

    # Execute order
    from app.brokers.models import OrderRequest, OrderSide, OrderType

    side = OrderSide.BUY if signal.side in ("BUY", "CLOSE") else OrderSide.SELL
    order_req = OrderRequest(
        symbol=target_symbol,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
    )

    try:
        result = adapter.place_order(order_req)
    except Exception as exc:
        # Record failed copy trade
        copy_trade = SocialCopyTrade(
            follow_id=0,  # no follow for manual copy
            signal_id=signal.id,
            follower_id=user.id,
            leader_id=signal.leader_id,
            symbol=target_symbol,
            side=signal.side,
            size_usd=size_usd,
            entry_price=current_price,
            broker_id=req.broker_id,
            status="failed",
            error=str(exc),
        )
        db.add(copy_trade)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Error al ejecutar orden: {exc}") from exc

    if not result.success:
        copy_trade = SocialCopyTrade(
            follow_id=0,
            signal_id=signal.id,
            follower_id=user.id,
            leader_id=signal.leader_id,
            symbol=target_symbol,
            side=signal.side,
            size_usd=size_usd,
            entry_price=current_price,
            broker_id=req.broker_id,
            status="failed",
            error=result.error or "Orden rechazada",
        )
        db.add(copy_trade)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Orden rechazada: {result.error}")

    # Record successful copy trade
    broker_order_id = result.order.broker_order_id if result.order else None
    copy_trade = SocialCopyTrade(
        follow_id=0,
        signal_id=signal.id,
        follower_id=user.id,
        leader_id=signal.leader_id,
        symbol=target_symbol,
        side=signal.side,
        size_usd=size_usd,
        entry_price=current_price,
        broker_id=req.broker_id,
        broker_order_id=broker_order_id,
        status="executed",
    )
    db.add(copy_trade)
    db.commit()
    db.refresh(copy_trade)

    return {
        "ok": True,
        "copy_trade_id": copy_trade.id,
        "broker": req.broker_id,
        "symbol": target_symbol,
        "side": signal.side,
        "size_usd": float(size_usd),
        "quantity": float(quantity),
        "entry_price": float(current_price),
        "broker_order_id": broker_order_id,
    }


@router.get("/my-copy-trades")
def my_copy_trades(
    user: Annotated[LocalUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Listar mis trades copiados."""
    rows = db.execute(
        select(SocialCopyTrade)
        .where(SocialCopyTrade.follower_id == user.id)
        .order_by(desc(SocialCopyTrade.created_at))
        .limit(limit)
    ).scalars().all()
    return [_copy_trade_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _leader_dict(leader: SocialLeader, include_stats: bool = False) -> dict:
    d = {
        "id": leader.id,
        "user_id": leader.user_id,
        "display_name": leader.display_name,
        "bio": leader.bio,
        "broker_id": leader.broker_id,
        "is_public": leader.is_public,
        "fee_percent": leader.fee_percent,
        "min_copy_amount_usd": leader.min_copy_amount_usd,
        "total_followers": leader.total_followers,
        "created_at": leader.created_at.isoformat() if leader.created_at else None,
    }
    if include_stats:
        d.update({
            "roi_30d": leader.roi_30d,
            "roi_90d": leader.roi_90d,
            "roi_all": leader.roi_all,
            "win_rate": leader.win_rate,
            "total_trades": leader.total_trades,
            "max_drawdown": leader.max_drawdown,
            "sharpe_ratio": leader.sharpe_ratio,
            "open_positions": leader.open_positions,
            "stats_updated_at": leader.stats_updated_at.isoformat() if leader.stats_updated_at else None,
        })
    return d


def _signal_dict(s: SocialSignal) -> dict:
    return {
        "id": s.id,
        "leader_id": s.leader_id,
        "symbol": s.symbol,
        "side": s.side,
        "size_pct": s.size_pct,
        "entry_price": float(s.entry_price) if s.entry_price else None,
        "stop_loss": float(s.stop_loss) if s.stop_loss else None,
        "take_profit": float(s.take_profit) if s.take_profit else None,
        "broker_id": s.broker_id,
        "status": s.status,
        "close_price": float(s.close_price) if s.close_price else None,
        "pnl_pct": s.pnl_pct,
        "comment": s.comment,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
    }


def _follow_dict(f: SocialFollow) -> dict:
    return {
        "id": f.id,
        "follower_id": f.follower_id,
        "leader_id": f.leader_id,
        "auto_copy": f.auto_copy,
        "copy_pct": f.copy_pct,
        "max_positions": f.max_positions,
        "symbol_filter": f.symbol_filter,
        "max_drawdown_pct": f.max_drawdown_pct,
        "active": f.active,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _copy_trade_dict(c: SocialCopyTrade) -> dict:
    return {
        "id": c.id,
        "signal_id": c.signal_id,
        "leader_id": c.leader_id,
        "symbol": c.symbol,
        "side": c.side,
        "size_usd": float(c.size_usd),
        "entry_price": float(c.entry_price) if c.entry_price else None,
        "broker_id": c.broker_id,
        "broker_order_id": c.broker_order_id,
        "status": c.status,
        "pnl": float(c.pnl),
        "error": c.error,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ---------------------------------------------------------------------------
# WebSocket broadcast helper (best-effort, no blocking)
# ---------------------------------------------------------------------------

_signal_subscribers: list = []  # list of asyncio.Queue


def _broadcast_signal(signal: SocialSignal, leader: SocialLeader) -> None:
    """Broadcast a new signal to all WS subscribers (best-effort)."""
    import asyncio
    data = {
        "type": "signal",
        "signal": _signal_dict(signal),
        "leader": {
            "id": leader.id,
            "display_name": leader.display_name,
            "broker_id": leader.broker_id,
            "roi_30d": leader.roi_30d,
            "win_rate": leader.win_rate,
            "total_followers": leader.total_followers,
        },
    }
    for queue in list(_signal_subscribers):
        try:
            # Put into each subscriber's queue (non-blocking)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(queue.put(data), loop)
            else:
                loop.run_until_complete(queue.put(data))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket — real-time signal feed
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect  # noqa: E402

@router.websocket("/ws/feed")
async def ws_social_feed(websocket: WebSocket):
    """WebSocket que envía nuevas señales en tiempo real a los clientes.

    Mensajes enviados:
    - {"type": "connected", "message": "Signal feed connected"}
    - {"type": "signal", "signal": {...}, "leader": {...}}
    - {"type": "signal_closed", "signal_id": 123, "close_price": 45000, "pnl_pct": 5.2}
    """
    import asyncio

    await websocket.accept()
    await websocket.send_json({"type": "connected", "message": "Signal feed connected"})

    # Create a queue for this subscriber
    queue: asyncio.Queue = asyncio.Queue()
    _signal_subscribers.append(queue)

    try:
        # Send recent active signals as initial snapshot
        db = next(get_db())
        try:
            recent = db.execute(
                select(SocialSignal)
                .join(SocialLeader, SocialSignal.leader_id == SocialLeader.id)
                .where(
                    SocialSignal.status == "active",
                    SocialLeader.is_public == True,  # noqa: E712
                )
                .order_by(desc(SocialSignal.created_at))
                .limit(20)
            ).scalars().all()

            for s in recent:
                leader = db.execute(
                    select(SocialLeader).where(SocialLeader.id == s.leader_id)
                ).scalar_one_or_none()
                await websocket.send_json({
                    "type": "signal",
                    "signal": _signal_dict(s),
                    "leader": {
                        "id": leader.id,
                        "display_name": leader.display_name,
                        "broker_id": leader.broker_id,
                        "roi_30d": leader.roi_30d,
                        "win_rate": leader.win_rate,
                        "total_followers": leader.total_followers,
                    } if leader else None,
                })
        finally:
            db.close()

        # Listen for new signals from the queue
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(data)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS social feed disconnected: %s", exc)
    finally:
        if queue in _signal_subscribers:
            _signal_subscribers.remove(queue)
