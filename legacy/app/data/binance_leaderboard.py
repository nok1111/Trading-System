"""Cliente para el leaderboard público de Binance Futures (Smart Money).

Usa los endpoints no oficiales de bapi.binance.com que alimenta la página
https://www.binance.com/en/futures-activity/leaderboard/top-ranking
"""

from typing import Any

import httpx

_BINANCE_BAPI = "https://www.binance.com"
_LEADERBOARD_RANK_ENDPOINTS = [
    "/bapi/futures/v3/public/future/leaderboard/getLeaderboardRank",
    "/bapi/futures/v2/public/future/leaderboard/getLeaderboardRank",
    "/bapi/futures/v1/public/future/leaderboard/getLeaderboardRank",
]
_OTHER_POSITION = "/bapi/futures/v1/public/future/leaderboard/getOtherPosition"
_OTHER_BASE_INFO = "/bapi/futures/v2/public/future/leaderboard/getOtherLeaderboardBaseInfo"
_SEARCH_NICKNAME = "/bapi/futures/v1/public/future/leaderboard/searchNickname"

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.8",
    "Cache-Control": "no-cache",
    "Clienttype": "web",
    "Lang": "en",
    "Origin": "https://www.binance.com",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

_PERIOD_MAP = {
    "24h": "1D",
    "3d": "3D",
    "7d": "7D",
    "30d": "30D",
    "90d": "90D",
    "1y": "1Y",
    "all": "ALL",
}


class BinanceLeaderboard:
    """Consulta el leaderboard de Smart Money de Binance Futures."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def get_top_traders(
        self,
        period: str = "7d",
        stat_type: str = "ROI",
        limit: int = 20,
    ) -> list[dict]:
        """Obtiene los top traders del leaderboard.

        Args:
            period: 24h, 3d, 7d, 30d, 90d, 1y, all
            stat_type: ROI o PNL
            limit: Número máximo de traders

        Returns:
            Lista de dicts con: rank, nickName, encryptedUid, roi, pnl,
            followerCount, positionShared, daysActive, winRate
        """
        period_key = _PERIOD_MAP.get(period.lower(), "7D")
        payload = {
            "tradeType": "PERPETUAL",
            "statisticsType": stat_type.upper(),
            "periodType": period_key,
            "isShared": True,
            "isTrader": False,
        }
        last_err = None
        for endpoint in _LEADERBOARD_RANK_ENDPOINTS:
            try:
                resp = httpx.post(
                    f"{_BINANCE_BAPI}{endpoint}",
                    json=payload,
                    headers=_HEADERS,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("success"):
                    rows = data.get("data", [])
                    traders = []
                    for row in rows[:limit]:
                        traders.append({
                            "rank": row.get("rank", 0),
                            "nickName": row.get("nickName", ""),
                            "encryptedUid": row.get("encryptedUid", ""),
                            "roi": float(row.get("roi", 0)),
                            "pnl": float(row.get("pnl", 0)),
                            "followerCount": row.get("followerCount", 0),
                            "positionShared": row.get("positionShared", False),
                            "daysActive": row.get("daysActive", 0),
                            "winRate": float(row.get("winRate", 0)),
                        })
                    return traders
            except Exception as exc:
                last_err = exc
                continue
        raise RuntimeError(f"Error al consultar leaderboard: {last_err}")

    def get_trader_positions(self, encrypted_uid: str) -> list[dict]:
        """Obtiene las posiciones abiertas de un trader específico.

        Args:
            encrypted_uid: ID encriptado del trader (del leaderboard)

        Returns:
            Lista de dicts con: symbol, side, entryPrice, markPrice, pnl,
            roe, amount, leverage, updateTimeStamp
        """
        payload = {
            "encryptedUid": encrypted_uid,
            "tradeType": "PERPETUAL",
        }
        try:
            resp = httpx.post(
                f"{_BINANCE_BAPI}{_OTHER_POSITION}",
                json=payload,
                headers=_HEADERS,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Error al consultar posiciones: {exc}") from exc

        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Binance rechazó la petición: {data.get('message', 'unknown')}")

        positions = data.get("data", {}).get("otherPositionRetList", [])
        result = []
        for p in positions:
            result.append({
                "symbol": p.get("symbol", ""),
                "side": p.get("side", ""),
                "entryPrice": float(p.get("entryPrice", 0)),
                "markPrice": float(p.get("markPrice", 0)),
                "pnl": float(p.get("pnl", 0)),
                "roe": float(p.get("roe", 0)),
                "amount": float(p.get("amount", 0)),
                "leverage": int(p.get("leverage", 1)),
                "updateTimeStamp": p.get("updateTimeStamp", 0),
            })
        return result

    def get_trader_info(self, encrypted_uid: str) -> dict:
        """Obtiene información básica de un trader.

        Args:
            encrypted_uid: ID encriptado del trader

        Returns:
            dict con nickName, roi, pnl, winRate, followers, etc.
        """
        payload = {"encryptedUid": encrypted_uid}
        try:
            resp = httpx.post(
                f"{_BINANCE_BAPI}{_OTHER_BASE_INFO}",
                json=payload,
                headers=_HEADERS,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Error al consultar info del trader: {exc}") from exc

        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Binance rechazó la petición: {data.get('message', 'unknown')}")

        info = data.get("data", {})
        return {
            "nickName": info.get("nickName", ""),
            "roi": float(info.get("roi", 0)),
            "pnl": float(info.get("pnl", 0)),
            "winRate": float(info.get("winRate", 0)),
            "followerCount": info.get("followerCount", 0),
            "daysActive": info.get("daysActive", 0),
            "positionShared": info.get("positionShared", False),
        }
