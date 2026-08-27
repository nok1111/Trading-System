"""Tax calculation engine — multi-country crypto tax reporting.

Supports lot-relief methods (FIFO, LIFO, HIFO, Specific ID) and generates
country-specific tax reports for ES, US, UK, DE, AU, CA, FR, JP.

Trade records use: symbol, side, quantity, price, timestamp, fee
"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

SUPPORTED_COUNTRIES = {
    "ES": "Spain",
    "US": "United States",
    "UK": "United Kingdom",
    "DE": "Germany",
    "AU": "Australia",
    "CA": "Canada",
    "FR": "France",
    "JP": "Japan",
}

COUNTRY_FLAGS = {
    "ES": "🇪🇸",
    "US": "🇺🇸",
    "UK": "🇬🇧",
    "DE": "🇩🇪",
    "AU": "🇦🇺",
    "CA": "🇨🇦",
    "FR": "🇫🇷",
    "JP": "🇯🇵",
}

# Basic tax-rate config per country (capital gains rate, allowance, currency)
COUNTRY_TAX_CONFIG: dict[str, dict[str, Any]] = {
    "ES": {
        "name": "Spain",
        "rate": Decimal("0.23"),  # savings base rate 19-28%, using mid
        "rate_brackets": [
            (Decimal("6000"), Decimal("0.19")),
            (Decimal("50000"), Decimal("0.21")),
            (Decimal("200000"), Decimal("0.23")),
            (None, Decimal("0.28")),
        ],
        "allowance": Decimal("0"),
        "currency": "EUR",
        "form_name": "IRPF — Ganancias Patrimoniales",
    },
    "US": {
        "name": "United States",
        "rate": Decimal("0.15"),  # long-term capital gains default
        "short_term_rate": Decimal("0.24"),  # ordinary income bracket
        "long_term_rate": Decimal("0.15"),
        "allowance": Decimal("0"),
        "currency": "USD",
        "form_name": "Form 8949 + Schedule D",
    },
    "UK": {
        "name": "United Kingdom",
        "rate": Decimal("0.10"),  # basic rate 10%, higher 20%
        "higher_rate": Decimal("0.20"),
        "allowance": Decimal("3000"),  # CGT allowance 2024/25
        "currency": "GBP",
        "form_name": "CGT — Capital Gains Tax",
    },
    "DE": {
        "name": "Germany",
        "rate": Decimal("0.25"),  # Abgeltungsteuer 25% + 5.5% solidarity
        "solidarity": Decimal("0.055"),
        "allowance": Decimal("600"),  # Sparer-Pauschbetrag
        "currency": "EUR",
        "form_name": "Abgeltungsteuer",
    },
    "AU": {
        "name": "Australia",
        "rate": Decimal("0.50"),  # 50% CGT discount for assets held >12 months
        "discount_rate": Decimal("0.50"),  # discount applied to gain
        "allowance": Decimal("0"),
        "currency": "AUD",
        "form_name": "CGT Schedule",
    },
    "CA": {
        "name": "Canada",
        "rate": Decimal("0.50"),  # 50% inclusion rate
        "inclusion_rate": Decimal("0.50"),
        "allowance": Decimal("0"),
        "currency": "CAD",
        "form_name": "Schedule 3 — Capital Gains",
    },
    "FR": {
        "name": "France",
        "rate": Decimal("0.30"),  # flat tax PFU 30% (17.2% social + 12.8% tax)
        "social_rate": Decimal("0.172"),
        "allowance": Decimal("305"),  # abatement for cession < 305€
        "currency": "EUR",
        "form_name": "Plus-Values Crypto",
    },
    "JP": {
        "name": "Japan",
        "rate": Decimal("0.20"),  # 15% income tax + 5% local tax
        "local_rate": Decimal("0.05"),
        "allowance": Decimal("0"),
        "currency": "JPY",
        "form_name": "Miscellaneous Income (Crypto)",
    },
}


@dataclass
class Lot:
    """A purchase lot that hasn't been fully matched yet."""

    trade_id: int | None
    symbol: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    timestamp: str


@dataclass
class Disposal:
    """A matched sell against one or more buy lots."""

    symbol: str
    buy_trade_id: int | None
    sell_trade_id: int | None
    quantity: Decimal
    buy_price: Decimal
    sell_price: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    buy_timestamp: str
    sell_timestamp: str
    proceeds: Decimal
    cost_basis: Decimal
    gain: Decimal
    holding_period_days: int
    income_type: str  # trading, staking, airdrop


@dataclass
class TaxSummary:
    total_proceeds: Decimal
    total_cost_basis: Decimal
    total_gains: Decimal
    total_losses: Decimal
    net_gain: Decimal
    estimated_tax: Decimal
    taxable_gain: Decimal
    country: str
    year: int
    method: str
    currency: str
    trade_count: int
    disposal_count: int


# ---------------------------------------------------------------------------
# TaxEngine
# ---------------------------------------------------------------------------


class TaxEngine:
    """Multi-country crypto tax calculation engine.

    Supports FIFO, LIFO, HIFO, and Specific ID lot-relief methods.
    Generates country-specific tax reports and CSV exports.
    """

    def __init__(self) -> None:
        self.countries = SUPPORTED_COUNTRIES
        self.tax_config = COUNTRY_TAX_CONFIG

    # -- Lot matching -------------------------------------------------------

    def calculate_capital_gains(
        self,
        trades: list[dict[str, Any]],
        method: str = "fifo",
    ) -> list[Disposal]:
        """Calculate capital gains by matching buys to sells.

        Args:
            trades: list of trade dicts with keys: symbol, side, quantity,
                    price, timestamp, fee, id (optional)
            method: 'fifo', 'lifo', 'hifo', or 'specific_id'

        Returns:
            list of Disposal records with gain/loss per matched lot.
        """
        method = method.lower()
        if method not in ("fifo", "lifo", "hifo", "specific_id"):
            raise ValueError(f"Unknown method: {method}. Use fifo, lifo, hifo, or specific_id")

        # Group trades by symbol
        by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in trades:
            sym = t.get("symbol", "")
            if not sym:
                continue
            by_symbol[sym].append(t)

        disposals: list[Disposal] = []

        for symbol, sym_trades in by_symbol.items():
            # Sort by timestamp for deterministic processing
            sym_trades_sorted = sorted(sym_trades, key=lambda t: self._parse_ts(t.get("timestamp")))

            open_lots: list[Lot] = []

            for trade in sym_trades_sorted:
                side = str(trade.get("side", "")).lower()
                qty = self._to_decimal(trade.get("quantity", 0))
                price = self._to_decimal(trade.get("price", 0))
                fee = self._to_decimal(trade.get("fee", trade.get("commission", 0)))
                ts = str(trade.get("timestamp", ""))
                trade_id = trade.get("id")

                if side in ("buy", "buy_long", "long"):
                    open_lots.append(
                        Lot(
                            trade_id=trade_id,
                            symbol=symbol,
                            quantity=qty,
                            price=price,
                            fee=fee,
                            timestamp=ts,
                        )
                    )
                elif side in ("sell", "sell_short", "short", "sell_cover"):
                    remaining = qty
                    # Match against open lots based on method
                    while remaining > 0 and open_lots:
                        lot = self._select_lot(open_lots, method, remaining)
                        if lot is None:
                            break

                        matched_qty = min(remaining, lot.quantity)

                        proceeds = matched_qty * price
                        # Allocate fees proportionally
                        sell_fee_alloc = fee * (matched_qty / qty) if qty > 0 else Decimal("0")
                        buy_fee_alloc = lot.fee * (matched_qty / lot.quantity) if lot.quantity > 0 else Decimal("0")
                        cost_basis = matched_qty * lot.price + buy_fee_alloc
                        proceeds_net = proceeds - sell_fee_alloc
                        gain = proceeds_net - cost_basis

                        holding_days = self._holding_period_days(lot.timestamp, ts)

                        income_type = self.classify_income(trade)

                        disposals.append(
                            Disposal(
                                symbol=symbol,
                                buy_trade_id=lot.trade_id,
                                sell_trade_id=trade_id,
                                quantity=matched_qty,
                                buy_price=lot.price,
                                sell_price=price,
                                buy_fee=buy_fee_alloc,
                                sell_fee=sell_fee_alloc,
                                buy_timestamp=lot.timestamp,
                                sell_timestamp=ts,
                                proceeds=proceeds_net,
                                cost_basis=cost_basis,
                                gain=gain,
                                holding_period_days=holding_days,
                                income_type=income_type,
                            )
                        )

                        remaining -= matched_qty
                        lot.quantity -= matched_qty
                        lot.fee -= buy_fee_alloc

                        if lot.quantity <= 0:
                            open_lots.remove(lot)
                # else: ignore unknown sides

        return disposals

    def _select_lot(
        self, lots: list[Lot], method: str, _qty: Decimal
    ) -> Lot | None:
        """Select the next lot to match based on the method."""
        if not lots:
            return None
        if method == "fifo":
            return lots[0]  # oldest first
        if method == "lifo":
            return lots[-1]  # newest first
        if method == "hifo":
            return max(lots, key=lambda l: l.price)  # highest cost first
        if method == "specific_id":
            # Without explicit lot IDs, fall back to FIFO
            return lots[0]
        return lots[0]

    # -- Income classification ----------------------------------------------

    def classify_income(self, trade: dict[str, Any]) -> str:
        """Classify a trade as trading, staking, or airdrop income.

        Uses metadata_json or strategy_name hints from the trade record.
        """
        metadata = trade.get("metadata_json") or trade.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        income_type = metadata.get("income_type", "")
        if income_type:
            return income_type

        strategy = str(trade.get("strategy_name", "") or "").lower()
        if "stake" in strategy or "stak" in income_type.lower():
            return "staking"
        if "airdrop" in strategy or "airdrop" in income_type.lower():
            return "airdrop"

        side = str(trade.get("side", "")).lower()
        symbol = str(trade.get("symbol", "")).upper()
        if "REWARD" in symbol or "STAKE" in symbol:
            return "staking"
        if "AIRDROP" in symbol:
            return "airdrop"

        return "trading"

    # -- Tax summary --------------------------------------------------------

    def generate_tax_summary(
        self,
        trades: list[dict[str, Any]],
        year: int,
        country: str,
        method: str = "fifo",
    ) -> dict[str, Any]:
        """Generate a tax summary with total gains, losses, net, estimated tax."""
        country = country.upper()
        if country not in self.tax_config:
            raise ValueError(f"Unsupported country: {country}")

        # Filter trades by year
        year_trades = self._filter_trades_by_year(trades, year)

        disposals = self.calculate_capital_gains(year_trades, method)

        total_proceeds = sum((d.proceeds for d in disposals), Decimal("0"))
        total_cost = sum((d.cost_basis for d in disposals), Decimal("0"))
        gains = sum((d.gain for d in disposals if d.gain > 0), Decimal("0"))
        losses = sum((d.gain for d in disposals if d.gain < 0), Decimal("0"))
        net = gains + losses  # losses are negative

        config = self.tax_config[country]
        taxable_gain, estimated_tax = self._compute_tax(country, net, gains, losses, disposals)

        summary = TaxSummary(
            total_proceeds=total_proceeds,
            total_cost_basis=total_cost,
            total_gains=gains,
            total_losses=losses,
            net_gain=net,
            estimated_tax=estimated_tax,
            taxable_gain=taxable_gain,
            country=country,
            year=year,
            method=method,
            currency=config["currency"],
            trade_count=len(year_trades),
            disposal_count=len(disposals),
        )

        return {
            "summary": asdict(summary),
            "disposals": [self._disposal_to_dict(d) for d in disposals],
            "country_config": {
                "name": config["name"],
                "currency": config["currency"],
                "form_name": config["form_name"],
                "rate": str(config["rate"]),
            },
        }

    def _compute_tax(
        self,
        country: str,
        net_gain: Decimal,
        gains: Decimal,
        losses: Decimal,
        disposals: list[Disposal],
    ) -> tuple[Decimal, Decimal]:
        """Compute taxable gain and estimated tax for a country."""
        config = self.tax_config[country]

        if country == "ES":
            # Spain: progressive brackets on savings base
            taxable = net_gain
            if taxable <= 0:
                return Decimal("0"), Decimal("0")
            tax = Decimal("0")
            remaining = taxable
            for threshold, rate in config["rate_brackets"]:
                if remaining <= 0:
                    break
                bracket_amount = min(remaining, threshold) if threshold else remaining
                tax += bracket_amount * rate
                remaining -= bracket_amount
            return taxable, tax

        if country == "US":
            # US: short-term (<=1yr) at ordinary, long-term (>1yr) at 15%
            short_term_gain = sum(
                (d.gain for d in disposals if d.gain > 0 and d.holding_period_days <= 365),
                Decimal("0"),
            )
            long_term_gain = sum(
                (d.gain for d in disposals if d.gain > 0 and d.holding_period_days > 365),
                Decimal("0"),
            )
            total_losses_abs = abs(losses)
            # Offset short-term first
            st_taxable = max(short_term_gain - total_losses_abs, Decimal("0"))
            remaining_loss = max(total_losses_abs - short_term_gain, Decimal("0"))
            lt_taxable = max(long_term_gain - remaining_loss, Decimal("0"))
            tax = st_taxable * config["short_term_rate"] + lt_taxable * config["long_term_rate"]
            return st_taxable + lt_taxable, tax

        if country == "UK":
            # UK: allowance then 10% basic, 20% higher
            allowance = config["allowance"]
            taxable = max(net_gain - allowance, Decimal("0"))
            if taxable <= Decimal("0"):
                return Decimal("0"), Decimal("0")
            # Simplified: assume basic rate for first 50k, higher above
            basic_band = Decimal("50000")
            basic_amount = min(taxable, basic_band)
            higher_amount = max(taxable - basic_band, Decimal("0"))
            tax = basic_amount * config["rate"] + higher_amount * config["higher_rate"]
            return taxable, tax

        if country == "DE":
            # Germany: Abgeltungsteuer 25% + 5.5% solidarity on the tax
            allowance = config["allowance"]
            taxable = max(net_gain - allowance, Decimal("0"))
            if taxable <= 0:
                return Decimal("0"), Decimal("0")
            base_tax = taxable * config["rate"]
            solidarity = base_tax * config["solidarity"]
            return taxable, base_tax + solidarity

        if country == "AU":
            # Australia: 50% discount on gains held >12 months
            discounted_gain = sum(
                (d.gain for d in disposals if d.gain > 0 and d.holding_period_days > 365),
                Decimal("0"),
            ) * (1 - config["discount_rate"])
            short_gain = sum(
                (d.gain for d in disposals if d.gain > 0 and d.holding_period_days <= 365),
                Decimal("0"),
            )
            taxable = max(discounted_gain + short_gain + losses, Decimal("0"))
            # Marginal rate ~ 32.5% simplified
            marginal_rate = Decimal("0.325")
            return taxable, taxable * marginal_rate

        if country == "CA":
            # Canada: 50% inclusion rate, taxed at marginal rate ~25%
            taxable = max(net_gain * config["inclusion_rate"], Decimal("0"))
            marginal_rate = Decimal("0.25")
            return taxable, taxable * marginal_rate

        if country == "FR":
            # France: flat tax PFU 30% (12.8% tax + 17.2% social)
            taxable = max(net_gain, Decimal("0"))
            if taxable <= 0:
                return Decimal("0"), Decimal("0")
            tax_rate = config["rate"]
            return taxable, taxable * tax_rate

        if country == "JP":
            # Japan: 15% income + 5% local on crypto gains
            taxable = max(net_gain, Decimal("0"))
            if taxable <= 0:
                return Decimal("0"), Decimal("0")
            tax = taxable * config["rate"]  # rate includes both
            return taxable, tax

        # Fallback
        taxable = max(net_gain, Decimal("0"))
        return taxable, taxable * config["rate"]

    # -- Full report --------------------------------------------------------

    def get_tax_report(
        self,
        user_id: int,
        year: int,
        country: str,
        trades: list[dict[str, Any]] | None = None,
        method: str = "fifo",
    ) -> dict[str, Any]:
        """Generate a full tax report for a user/year/country.

        If trades are not provided, they should be loaded from DB by the caller.
        """
        country = country.upper()
        if country not in self.tax_config:
            raise ValueError(f"Unsupported country: {country}")

        trades = trades or []
        summary_data = self.generate_tax_summary(trades, year, country, method)

        # Add country-specific form data
        country_form = self._generate_country_form(country, summary_data["disposals"], year)

        report = {
            "user_id": user_id,
            "year": year,
            "country": country,
            "country_name": self.tax_config[country]["name"],
            "method": method,
            "currency": self.tax_config[country]["currency"],
            "form_name": self.tax_config[country]["form_name"],
            "summary": summary_data["summary"],
            "disposals": summary_data["disposals"],
            "country_form": country_form,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        return report

    def _generate_country_form(
        self, country: str, disposals: list[dict[str, Any]], year: int
    ) -> dict[str, Any]:
        """Dispatch to the country-specific form generator."""
        generators = {
            "US": self.generate_form_8949,
            "ES": self.generate_irpf_es,
            "UK": self.generate_uk_cgt,
            "DE": self.generate_de_abgeeltung,
            "AU": self.generate_au_cgt,
            "CA": self.generate_ca_schedule3,
            "FR": self.generate_fr_plus_value,
            "JP": self.generate_jp_crypto_tax,
        }
        gen = generators.get(country)
        if gen is None:
            return {"error": f"No form generator for {country}"}
        return gen(disposals)

    # -- Country-specific generators ----------------------------------------

    def generate_form_8949(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """US Form 8949 — Sales and Other Dispositions of Capital Assets.

        Columns: Description, Date Acquired, Date Sold, Proceeds,
                 Cost Basis, Gain/Loss, Holding Period.
        """
        rows = []
        for d in disposals:
            holding = "Long-term" if d["holding_period_days"] > 365 else "Short-term"
            rows.append({
                "description": f"{d['symbol']} — Crypto asset",
                "date_acquired": d["buy_timestamp"][:10] if d["buy_timestamp"] else "",
                "date_sold": d["sell_timestamp"][:10] if d["sell_timestamp"] else "",
                "proceeds": str(d["proceeds"]),
                "cost_basis": str(d["cost_basis"]),
                "gain_loss": str(d["gain"]),
                "holding_period": holding,
                "code": "D" if holding == "Long-term" else "A",  # D=LT covered, A=ST covered
            })

        total_proceeds = sum((self._to_decimal(r["proceeds"]) for r in rows), Decimal("0"))
        total_cost = sum((self._to_decimal(r["cost_basis"]) for r in rows), Decimal("0"))
        total_gain = total_proceeds - total_cost

        return {
            "form": "Form 8949",
            "title": "Sales and Other Dispositions of Capital Assets",
            "rows": rows,
            "totals": {
                "proceeds": str(total_proceeds),
                "cost_basis": str(total_cost),
                "gain_loss": str(total_gain),
            },
            "notes": "Report on Schedule D. Short-term (<=1yr) and long-term (>1yr) separated.",
        }

    def generate_irpf_es(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """Spain IRPF — Ganancias y Pérdidas Patrimoniales.

        Crypto gains go in the savings tax base (base del ahorro).
        """
        gains = sum((self._to_decimal(d["gain"]) for d in disposals if d["gain"] > 0), Decimal("0"))
        losses = sum((self._to_decimal(d["gain"]) for d in disposals if d["gain"] < 0), Decimal("0"))
        net = gains + losses

        # Apply progressive brackets
        config = self.tax_config["ES"]
        tax = Decimal("0")
        remaining = max(net, Decimal("0"))
        brackets_applied = []
        for threshold, rate in config["rate_brackets"]:
            if remaining <= 0:
                break
            bracket_amount = min(remaining, threshold) if threshold else remaining
            bracket_tax = bracket_amount * rate
            tax += bracket_tax
            brackets_applied.append({
                "bracket": f"Up to {threshold}" if threshold else "Above 200000",
                "amount": str(bracket_amount),
                "rate": str(rate),
                "tax": str(bracket_tax),
            })
            remaining -= bracket_amount

        return {
            "form": "IRPF — Ganancias Patrimoniales",
            "title": "Spain IRPF — Capital Gains (Savings Base)",
            "section": "Base Imponible del Ahorro",
            "total_gains": str(gains),
            "total_losses": str(losses),
            "net_gain": str(net),
            "brackets": brackets_applied,
            "total_tax": str(tax),
            "notes": "Crypto gains taxed in savings base. Losses can offset gains within same year.",
        }

    def generate_uk_cgt(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """UK Capital Gains Tax report."""
        config = self.tax_config["UK"]
        gains = sum((self._to_decimal(d["gain"]) for d in disposals if d["gain"] > 0), Decimal("0"))
        losses = sum((self._to_decimal(d["gain"]) for d in disposals if d["gain"] < 0), Decimal("0"))
        net = gains + losses
        allowance = config["allowance"]
        taxable = max(net - allowance, Decimal("0"))

        basic_band = Decimal("50000")
        basic_amount = min(taxable, basic_band)
        higher_amount = max(taxable - basic_band, Decimal("0"))
        tax = basic_amount * config["rate"] + higher_amount * config["higher_rate"]

        return {
            "form": "CGT",
            "title": "UK Capital Gains Tax",
            "total_gains": str(gains),
            "total_losses": str(losses),
            "net_gain": str(net),
            "annual_allowance": str(allowance),
            "taxable_gain": str(taxable),
            "basic_rate_amount": str(basic_amount),
            "basic_rate_tax": str(basic_amount * config["rate"]),
            "higher_rate_amount": str(higher_amount),
            "higher_rate_tax": str(higher_amount * config["higher_rate"]),
            "total_tax": str(tax),
            "notes": "Annual exempt amount (AEA) deducted. Basic rate 10%, higher rate 20%.",
        }

    def generate_de_abgeeltung(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """Germany Abgeltungsteuer report."""
        config = self.tax_config["DE"]
        net = sum((self._to_decimal(d["gain"]) for d in disposals), Decimal("0"))
        allowance = config["allowance"]
        taxable = max(net - allowance, Decimal("0"))
        base_tax = taxable * config["rate"]
        solidarity = base_tax * config["solidarity"]
        church_tax = Decimal("0")  # optional, not computed

        return {
            "form": "Abgeltungsteuer",
            "title": "Germany — Flat Rate Withholding Tax",
            "net_gain": str(net),
            "allowance": str(allowance),
            "taxable_gain": str(taxable),
            "base_tax_25pct": str(base_tax),
            "solidarity_5_5pct": str(solidarity),
            "church_tax": str(church_tax),
            "total_tax": str(base_tax + solidarity + church_tax),
            "notes": "25% Abgeltungsteuer + 5.5% solidarity surcharge. Church tax optional (8-9%).",
        }

    def generate_au_cgt(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """Australia CGT report with 50% discount for >12 month holds."""
        config = self.tax_config["AU"]
        long_gains = sum(
            (self._to_decimal(d["gain"]) for d in disposals if d["gain"] > 0 and d["holding_period_days"] > 365),
            Decimal("0"),
        )
        short_gains = sum(
            (self._to_decimal(d["gain"]) for d in disposals if d["gain"] > 0 and d["holding_period_days"] <= 365),
            Decimal("0"),
        )
        losses = sum(
            (self._to_decimal(d["gain"]) for d in disposals if d["gain"] < 0),
            Decimal("0"),
        )
        discounted = long_gains * (1 - config["discount_rate"])
        net = discounted + short_gains + losses
        taxable = max(net, Decimal("0"))
        marginal_rate = Decimal("0.325")
        tax = taxable * marginal_rate

        return {
            "form": "CGT Schedule",
            "title": "Australia — Capital Gains Tax",
            "long_term_gains": str(long_gains),
            "short_term_gains": str(short_gains),
            "losses": str(losses),
            "discount_applied": str(long_gains * config["discount_rate"]),
            "discounted_gains": str(discounted),
            "taxable_gain": str(taxable),
            "marginal_rate": str(marginal_rate),
            "estimated_tax": str(tax),
            "notes": "50% CGT discount for assets held >12 months. Marginal rate applied.",
        }

    def generate_ca_schedule3(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """Canada Schedule 3 — Capital Gains report."""
        config = self.tax_config["CA"]
        net = sum((self._to_decimal(d["gain"]) for d in disposals), Decimal("0"))
        inclusion = config["inclusion_rate"]
        taxable = max(net * inclusion, Decimal("0"))
        marginal_rate = Decimal("0.25")
        tax = taxable * marginal_rate

        return {
            "form": "Schedule 3",
            "title": "Canada — Capital Gains (Schedule 3)",
            "total_gains_losses": str(net),
            "inclusion_rate": str(inclusion),
            "taxable_capital_gain": str(taxable),
            "marginal_rate": str(marginal_rate),
            "estimated_tax": str(tax),
            "notes": "50% of capital gains are taxable (inclusion rate). Reported on Schedule 3.",
        }

    def generate_fr_plus_value(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """France Plus-Values crypto report (PFU flat tax)."""
        config = self.tax_config["FR"]
        net = sum((self._to_decimal(d["gain"]) for d in disposals), Decimal("0"))
        taxable = max(net, Decimal("0"))
        tax = taxable * config["rate"]
        social = taxable * config["social_rate"]
        income_tax = taxable * (config["rate"] - config["social_rate"])

        return {
            "form": "Plus-Values Crypto",
            "title": "France — Crypto Capital Gains (PFU)",
            "net_gain": str(net),
            "taxable_gain": str(taxable),
            "social_contributions_17_2pct": str(social),
            "income_tax_12_8pct": str(income_tax),
            "total_flat_tax_30pct": str(tax),
            "notes": "PFU (Prélèvement Forfaitaire Unique) 30% = 12.8% tax + 17.2% social contributions.",
        }

    def generate_jp_crypto_tax(self, disposals: list[dict[str, Any]]) -> dict[str, Any]:
        """Japan crypto tax report (Miscellaneous Income)."""
        config = self.tax_config["JP"]
        net = sum((self._to_decimal(d["gain"]) for d in disposals), Decimal("0"))
        taxable = max(net, Decimal("0"))
        income_tax = taxable * Decimal("0.15")
        local_tax = taxable * config["local_rate"]
        total = income_tax + local_tax

        return {
            "form": "Miscellaneous Income",
            "title": "Japan — Crypto Asset Gains (Miscellaneous Income)",
            "net_gain": str(net),
            "taxable_income": str(taxable),
            "national_income_tax_15pct": str(income_tax),
            "local_inhabitant_tax_5pct": str(local_tax),
            "total_tax": str(total),
            "notes": "Crypto gains classified as miscellaneous income. 15% national + 5% local tax.",
        }

    # -- CSV export ---------------------------------------------------------

    def export_csv(self, report: dict[str, Any]) -> str:
        """Export a tax report as a CSV string.

        Exports the disposals table with all columns.
        """
        disposals = report.get("disposals", [])
        if not disposals:
            return "No data to export\n"

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Symbol",
            "Buy Date",
            "Sell Date",
            "Quantity",
            "Buy Price",
            "Sell Price",
            "Buy Fee",
            "Sell Fee",
            "Proceeds",
            "Cost Basis",
            "Gain/Loss",
            "Holding Period (days)",
            "Income Type",
        ])

        for d in disposals:
            writer.writerow([
                d.get("symbol", ""),
                (d.get("buy_timestamp") or "")[:10],
                (d.get("sell_timestamp") or "")[:10],
                d.get("quantity", ""),
                d.get("buy_price", ""),
                d.get("sell_price", ""),
                d.get("buy_fee", ""),
                d.get("sell_fee", ""),
                d.get("proceeds", ""),
                d.get("cost_basis", ""),
                d.get("gain", ""),
                d.get("holding_period_days", ""),
                d.get("income_type", ""),
            ])

        # Summary footer
        summary = report.get("summary", {})
        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow(["Country", report.get("country", "")])
        writer.writerow(["Year", report.get("year", "")])
        writer.writerow(["Method", report.get("method", "")])
        writer.writerow(["Currency", report.get("currency", "")])
        writer.writerow(["Total Proceeds", summary.get("total_proceeds", "")])
        writer.writerow(["Total Cost Basis", summary.get("total_cost_basis", "")])
        writer.writerow(["Total Gains", summary.get("total_gains", "")])
        writer.writerow(["Total Losses", summary.get("total_losses", "")])
        writer.writerow(["Net Gain", summary.get("net_gain", "")])
        writer.writerow(["Taxable Gain", summary.get("taxable_gain", "")])
        writer.writerow(["Estimated Tax", summary.get("estimated_tax", "")])

        return output.getvalue()

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _to_decimal(val: Any) -> Decimal:
        if isinstance(val, Decimal):
            return val
        if val is None:
            return Decimal("0")
        try:
            return Decimal(str(val))
        except Exception:
            return Decimal("0")

    @staticmethod
    def _parse_ts(ts: Any) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if not ts:
            return datetime.min
        s = str(ts).strip().replace(" ", "T")
        # Try with timezone
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s[:len(fmt) + 5] if "%f" in fmt else s[:19], fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return datetime.min

    @staticmethod
    def _holding_period_days(buy_ts: str, sell_ts: str) -> int:
        buy = TaxEngine._parse_ts(buy_ts)
        sell = TaxEngine._parse_ts(sell_ts)
        delta = sell - buy
        return max(delta.days, 0)

    @staticmethod
    def _filter_trades_by_year(trades: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
        """Filter trades to only those in the given calendar year."""
        result = []
        for t in trades:
            ts = t.get("timestamp")
            dt = TaxEngine._parse_ts(ts)
            if dt.year == year:
                result.append(t)
        return result

    @staticmethod
    def _disposal_to_dict(d: Disposal) -> dict[str, Any]:
        return {
            "symbol": d.symbol,
            "buy_trade_id": d.buy_trade_id,
            "sell_trade_id": d.sell_trade_id,
            "quantity": str(d.quantity),
            "buy_price": str(d.buy_price),
            "sell_price": str(d.sell_price),
            "buy_fee": str(d.buy_fee),
            "sell_fee": str(d.sell_fee),
            "buy_timestamp": d.buy_timestamp,
            "sell_timestamp": d.sell_timestamp,
            "proceeds": str(d.proceeds),
            "cost_basis": str(d.cost_basis),
            "gain": str(d.gain),
            "holding_period_days": d.holding_period_days,
            "income_type": d.income_type,
        }


# Singleton instance
_tax_engine: TaxEngine | None = None


def get_tax_engine() -> TaxEngine:
    """Get the singleton TaxEngine instance."""
    global _tax_engine
    if _tax_engine is None:
        _tax_engine = TaxEngine()
    return _tax_engine
