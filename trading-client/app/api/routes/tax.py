"""Tax Studio endpoints — multi-country crypto tax calculation and reporting.

Endpoints:
  GET  /api/tax/countries              — list supported countries with names
  POST /api/tax/calculate              — calculate tax report (auth)
  GET  /api/tax/reports                — list saved reports (auth)
  GET  /api/tax/reports/{id}           — report detail (auth)
  GET  /api/tax/reports/{id}/csv       — download CSV (auth)
  GET  /api/tax/estimated-liability    — real-time estimate (auth)
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.database.models.tax_report import TaxReport as TaxReportModel
from app.database.session import SessionLocal
from app.services.auth import LocalUser, get_current_user
from app.services.tax_engine import COUNTRY_FLAGS, SUPPORTED_COUNTRIES, get_tax_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tax", tags=["tax"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CalculateRequest(BaseModel):
    year: int
    country: str
    method: str = "fifo"


class SaveReportRequest(BaseModel):
    year: int
    country: str
    method: str = "fifo"
    report_json: str  # pre-calculated report as JSON string


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _load_user_trades(user_id: int, year: int) -> list[dict]:
    """Load trades for a user from the DB, filtered by year.

    Returns a list of trade dicts compatible with the TaxEngine.
    """
    from app.database.models.trade import Trade

    db = SessionLocal()
    try:
        trades = (
            db.query(Trade)
            .filter(Trade.user_id == user_id)
            .order_by(Trade.timestamp)
            .all()
        )
        result = []
        for t in trades:
            result.append({
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": str(t.quantity),
                "price": str(t.price),
                "fee": str(t.commission),
                "timestamp": t.timestamp.isoformat() if t.timestamp else "",
                "strategy_name": t.strategy_name,
                "metadata_json": t.metadata_json or {},
            })
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/countries")
def list_countries() -> dict:
    """List all supported countries with names and flags."""
    countries = []
    for code, name in sorted(SUPPORTED_COUNTRIES.items()):
        countries.append({
            "code": code,
            "name": name,
            "flag": COUNTRY_FLAGS.get(code, ""),
        })
    return {"countries": countries}


@router.post("/calculate")
def calculate_tax(
    req: CalculateRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Calculate a tax report for the given year, country, and method.

    Loads the user's trades from the DB and runs the tax engine.
    Does NOT save the report — use the save endpoint for that.
    """
    country = req.country.upper()
    if country not in SUPPORTED_COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Unsupported country: {country}")

    method = req.method.lower()
    if method not in ("fifo", "lifo", "hifo", "specific_id"):
        raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")

    trades = _load_user_trades(current_user.id, req.year)
    engine = get_tax_engine()
    report = engine.get_tax_report(
        user_id=current_user.id,
        year=req.year,
        country=country,
        trades=trades,
        method=method,
    )
    return report


@router.post("/reports")
def save_report(
    req: SaveReportRequest,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Save a calculated tax report to the database."""
    country = req.country.upper()
    if country not in SUPPORTED_COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Unsupported country: {country}")

    db = SessionLocal()
    try:
        report = TaxReportModel(
            user_id=current_user.id,
            year=req.year,
            country=country,
            method=req.method.lower(),
            report_json=req.report_json,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return {
            "id": report.id,
            "user_id": report.user_id,
            "year": report.year,
            "country": report.country,
            "method": report.method,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save tax report: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save report") from exc
    finally:
        db.close()


@router.get("/reports")
def list_reports(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    year: Annotated[int | None, Query()] = None,
) -> dict:
    """List saved tax reports for the current user."""
    db = SessionLocal()
    try:
        query = db.query(TaxReportModel).filter(TaxReportModel.user_id == current_user.id)
        if year is not None:
            query = query.filter(TaxReportModel.year == year)
        reports = query.order_by(TaxReportModel.created_at.desc()).all()
        return {
            "reports": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "year": r.year,
                    "country": r.country,
                    "country_name": SUPPORTED_COUNTRIES.get(r.country, r.country),
                    "method": r.method,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reports
            ]
        }
    finally:
        db.close()


@router.get("/reports/{report_id}")
def get_report(
    report_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> dict:
    """Get a saved tax report by ID (full JSON)."""
    db = SessionLocal()
    try:
        report = (
            db.query(TaxReportModel)
            .filter(TaxReportModel.id == report_id, TaxReportModel.user_id == current_user.id)
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        try:
            report_data = json.loads(report.report_json) if report.report_json else {}
        except json.JSONDecodeError:
            report_data = {}

        return {
            "id": report.id,
            "user_id": report.user_id,
            "year": report.year,
            "country": report.country,
            "country_name": SUPPORTED_COUNTRIES.get(report.country, report.country),
            "method": report.method,
            "report": report_data,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
    finally:
        db.close()


@router.get("/reports/{report_id}/csv", response_class=PlainTextResponse)
def download_report_csv(
    report_id: int,
    current_user: Annotated[LocalUser, Depends(get_current_user)],
) -> str:
    """Download a saved tax report as CSV."""
    db = SessionLocal()
    try:
        report = (
            db.query(TaxReportModel)
            .filter(TaxReportModel.id == report_id, TaxReportModel.user_id == current_user.id)
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        try:
            report_data = json.loads(report.report_json) if report.report_json else {}
        except json.JSONDecodeError:
            report_data = {}

        engine = get_tax_engine()
        csv_str = engine.export_csv(report_data)
        return csv_str
    finally:
        db.close()


@router.get("/estimated-liability")
def estimated_liability(
    current_user: Annotated[LocalUser, Depends(get_current_user)],
    year: Annotated[int, Query()] = 0,
    country: Annotated[str, Query()] = "US",
    method: Annotated[str, Query()] = "fifo",
) -> dict:
    """Get a real-time estimated tax liability for the current year.

    Loads trades and computes a quick summary without saving.
    """
    import datetime as _dt

    if year == 0:
        year = _dt.datetime.utcnow().year

    country = country.upper()
    if country not in SUPPORTED_COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Unsupported country: {country}")

    method = method.lower()
    if method not in ("fifo", "lifo", "hifo", "specific_id"):
        raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")

    trades = _load_user_trades(current_user.id, year)
    engine = get_tax_engine()
    summary = engine.generate_tax_summary(trades, year, country, method)

    return {
        "year": year,
        "country": country,
        "method": method,
        "summary": summary["summary"],
        "trade_count": len(trades),
        "disposal_count": summary["summary"]["disposal_count"],
    }
