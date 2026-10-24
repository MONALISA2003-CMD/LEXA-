"""Deterministic Uganda tax estimates from URA guidance available by 2026-10-23.

This module never submits a return, changes a taxpayer's registration status, or
contacts URA, a bank, mobile-money provider, or payment gateway. Estimates are
for bookkeeping and planning; actual tax treatment still depends on eligibility,
supply classification, registration, and the facts of the taxpayer.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MONEY = Decimal("0.01")
ZERO = Decimal("0")
VAT_STANDARD_RATE = Decimal("18")
PRESUMPTIVE_MAX_TURNOVER = Decimal("150000000")
# Published in URA's Ask the Commissioner General 41 on 23 October 2026.
# This is displayed only as the newest URA FAQ value, not used to auto-register
# a business, turn VAT on/off, or make a legal eligibility decision.
VAT_THRESHOLD_LATEST_URA_FAQ = Decimal("300000000")
VAT_THRESHOLD_OTHER_OFFICIAL_PAGE = Decimal("250000000")

EXCLUDED_PRESUMPTIVE_SECTORS = {
    "MEDICAL",
    "DENTAL",
    "ARCHITECTURAL",
    "ENGINEERING",
    "ACCOUNTING",
    "LEGAL",
    "OTHER_PROFESSIONAL",
    "PUBLIC_ENTERTAINMENT",
    "PUBLIC_UTILITY",
    "CONSTRUCTION",
}


def _money(value: Decimal | int | str) -> Decimal:
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Amount must be a finite number")
        return number.quantize(MONEY, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Amount is outside the supported numeric range") from exc


def _serial(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def calculate_vat(amount: Decimal | int | str, *, price_includes_tax: bool = False,
                  rate_percent: Decimal | int | str = VAT_STANDARD_RATE) -> dict[str, Any]:
    """Calculate VAT for a confirmed VAT treatment, not determine treatment."""
    amount = _money(amount)
    rate = Decimal(str(rate_percent))
    if amount < ZERO:
        raise ValueError("Amount cannot be negative")
    if not rate.is_finite() or rate < ZERO or rate > Decimal("100"):
        raise ValueError("Tax rate must be between 0 and 100 percent")
    factor = rate / Decimal("100")
    if price_includes_tax:
        total = amount
        taxable_base = _money(total / (Decimal("1") + factor)) if factor else total
        tax = _money(total - taxable_base)
    else:
        taxable_base = amount
        tax = _money(taxable_base * factor)
        total = _money(taxable_base + tax)
    return {
        "eligible": True,
        "amount": _serial(amount),
        "taxable_base": _serial(taxable_base),
        "rate_percent": str(rate),
        "price_includes_tax": bool(price_includes_tax),
        "tax_amount": _serial(tax),
        "total_amount": _serial(total),
        "formula": "Extract tax from the tax-inclusive amount" if price_includes_tax else "Taxable base × rate",
        "note": "Use only for a supply confirmed to have this VAT treatment. Zero-rated and exempt supplies are not interchangeable.",
    }


def calculate_presumptive_tax(annual_turnover: Decimal | int | str, *, records_kept: bool,
                              resident_taxpayer: bool = True, sector: str = "GENERAL") -> dict[str, Any]:
    """Estimate annual presumptive tax from the URA FAQ published 2026-10-23."""
    turnover = _money(annual_turnover)
    normalized_sector = str(sector or "GENERAL").strip().upper()
    if turnover < ZERO:
        raise ValueError("Annual turnover cannot be negative")
    reasons: list[str] = []
    if not resident_taxpayer:
        reasons.append("The cited presumptive regime is for qualifying resident taxpayers.")
    if normalized_sector in EXCLUDED_PRESUMPTIVE_SECTORS:
        reasons.append("This sector is listed by URA as excluded from the presumptive regime.")
    if turnover > PRESUMPTIVE_MAX_TURNOVER:
        reasons.append("Annual turnover exceeds UGX 150 million, the ceiling stated in the URA guidance.")
    if reasons:
        return {
            "eligible": False,
            "tax_type": "PRESUMPTIVE_INCOME_TAX",
            "annual_turnover": _serial(turnover),
            "records_kept": records_kept,
            "tax_amount": None,
            "reasons": reasons,
            "note": "LEXA does not select another income-tax regime automatically. Confirm the correct regime with URA or a qualified tax adviser.",
        }

    if turnover <= Decimal("10000000"):
        tax = ZERO
        band = "0–10m"
        formula = "Nil"
    elif turnover <= Decimal("30000000"):
        band = "10m–30m"
        if records_kept:
            tax = (turnover - Decimal("10000000")) * Decimal("0.004")
            formula = "0.4% of annual turnover above UGX 10 million"
        else:
            tax = Decimal("80000")
            formula = "Fixed amount of UGX 80,000"
    elif turnover <= Decimal("50000000"):
        band = "30m–50m"
        if records_kept:
            tax = Decimal("80000") + (turnover - Decimal("30000000")) * Decimal("0.005")
            formula = "UGX 80,000 + 0.5% of turnover above UGX 30 million"
        else:
            tax = Decimal("200000")
            formula = "Fixed amount of UGX 200,000"
    elif turnover <= Decimal("80000000"):
        band = "50m–80m"
        if records_kept:
            tax = Decimal("180000") + (turnover - Decimal("50000000")) * Decimal("0.006")
            formula = "UGX 180,000 + 0.6% of turnover above UGX 50 million"
        else:
            tax = Decimal("400000")
            formula = "Fixed amount of UGX 400,000"
    else:
        band = "80m–150m"
        if records_kept:
            tax = Decimal("360000") + (turnover - Decimal("80000000")) * Decimal("0.007")
            formula = "UGX 360,000 + 0.7% of turnover above UGX 80 million"
        else:
            tax = Decimal("900000")
            formula = "Fixed amount of UGX 900,000"

    tax = _money(tax)
    return {
        "eligible": True,
        "tax_type": "PRESUMPTIVE_INCOME_TAX",
        "annual_turnover": _serial(turnover),
        "records_kept": records_kept,
        "band": band,
        "tax_amount": _serial(tax),
        "formula": formula,
        "note": "Annual planning estimate only; eligibility and the applicable assessment must be confirmed for the taxpayer.",
    }


def calculate_paye(monthly_chargeable_income: Decimal | int | str, *, residency: str = "RESIDENT") -> dict[str, Any]:
    """Estimate monthly PAYE using the published FY 2026/27 schedules.

    The updated resident bands took effect 1 July 2026. The URA PAYE guidance
    page publishes a separate non-resident schedule; it is never inferred from
    the resident bands.
    """
    income = _money(monthly_chargeable_income)
    if income < ZERO:
        raise ValueError("Chargeable income cannot be negative")
    normalized_residency = str(residency or "RESIDENT").strip().upper()
    if normalized_residency not in {"RESIDENT", "NON_RESIDENT"}:
        raise ValueError("Choose resident or non-resident employee status")

    if normalized_residency == "NON_RESIDENT":
        # The published non-resident schedule is separate: no tax-free band.
        if income <= Decimal("335000"):
            tax = income * Decimal("0.10")
            band = "0–335,000"
            formula = "10% of monthly chargeable income (non-resident schedule)"
        elif income <= Decimal("410000"):
            tax = Decimal("33500") + (income - Decimal("335000")) * Decimal("0.20")
            band = "335,000–410,000"
            formula = "UGX 33,500 + 20% above UGX 335,000"
        else:
            tax = Decimal("48500") + (income - Decimal("410000")) * Decimal("0.30")
            if income > Decimal("10000000"):
                tax += (income - Decimal("10000000")) * Decimal("0.10")
            band = "Above 410,000"
            formula = "UGX 48,500 + 30% above UGX 410,000; add 10% above UGX 10 million"
    elif income <= Decimal("335000"):
        tax = ZERO
        band = "0–335,000"
        formula = "Nil"
    elif income <= Decimal("410000"):
        tax = (income - Decimal("335000")) * Decimal("0.20")
        band = "335,000–410,000"
        formula = "20% of chargeable income above UGX 335,000"
    elif income <= Decimal("485000"):
        tax = Decimal("15000") + (income - Decimal("410000")) * Decimal("0.25")
        band = "410,000–485,000"
        formula = "UGX 15,000 + 25% above UGX 410,000"
    elif income <= Decimal("10000000"):
        tax = Decimal("33750") + (income - Decimal("485000")) * Decimal("0.30")
        band = "485,000–10,000,000"
        formula = "UGX 33,750 + 30% above UGX 485,000"
    else:
        tax = (Decimal("33750") + (income - Decimal("485000")) * Decimal("0.30")
               + (income - Decimal("10000000")) * Decimal("0.10"))
        band = "Above 10,000,000"
        formula = "UGX 33,750 + 30% above UGX 485,000 + 10% above UGX 10 million"
    tax = _money(tax)
    return {
        "eligible": True,
        "tax_type": f"{normalized_residency}_MONTHLY_PAYE",
        "residency": normalized_residency,
        "monthly_chargeable_income": _serial(income),
        "band": band,
        "tax_amount": _serial(tax),
        "formula": formula,
        "note": "Monthly PAYE estimate using the URA-published schedule for the selected residency. Confirm payroll-specific rules and deductions before filing.",
    }



def calculate_withholding(amount: Decimal | int | str, *, withholding_agent: bool,
                          withholding_kind: str, payee_residency: str = "RESIDENT") -> dict[str, Any]:
    """Estimate cited WHT guidance; only applies when the business is an agent."""
    base = _money(amount)
    if base < ZERO:
        raise ValueError("Amount cannot be negative")
    if withholding_kind not in {"TAXABLE_SUPPLY", "PROFESSIONAL_OR_MANAGEMENT"}:
        raise ValueError("Unsupported withholding category")
    residency = str(payee_residency or "RESIDENT").upper()
    if residency not in {"RESIDENT", "NON_RESIDENT"}:
        raise ValueError("Choose resident or non-resident payee status")
    if not withholding_agent:
        return {
            "eligible": False,
            "tax_type": "WITHHOLDING_TAX",
            "basis_amount": _serial(base),
            "tax_amount": None,
            "note": "The cited URA guidance applies withholding duties where the business is appointed as a withholding-tax agent. This estimate does not decide appointment status.",
        }
    if withholding_kind == "TAXABLE_SUPPLY":
        if base <= Decimal("1000000"):
            rate = ZERO
            formula = "No withholding under this cited threshold for an amount not exceeding UGX 1 million"
        else:
            rate = Decimal("6")
            formula = "6% of the full payment when the payment exceeds UGX 1 million"
            return {
                "eligible": True,
                "tax_type": "WITHHOLDING_TAX",
                "basis_amount": _serial(base),
                "rate_percent": str(rate),
                "tax_amount": _serial(_money(base * rate / Decimal("100"))),
                "formula": formula,
                "note": "Planning estimate only. The threshold is a condition for applying the rate, not a deduction from the taxable base; confirm supply classification and statutory exceptions before withholding.",
            }
    else:
        rate = Decimal("6") if residency == "RESIDENT" else Decimal("15")
        formula = f"{rate}% for {residency.lower()} management/professional service recipient"
    return {
        "eligible": True,
        "tax_type": "WITHHOLDING_TAX",
        "basis_amount": _serial(base),
        "rate_percent": str(rate),
        "tax_amount": _serial(_money(base * rate / Decimal("100"))),
        "formula": formula,
        "note": "Confirm agent status, the legal tax base, exemptions, and recipient classification before withholding.",
    }


def tax_reference_payload() -> dict[str, Any]:
    """Return the dated, source-attributed reference data used by the calculators."""
    return {
        "reference_date": "2026-10-23",
        "provider_integrations": False,
        "payment_handling": "RECORD_ONLY",
        "efris_mode": "MANUAL_RECORD_ONLY",
        "vat": {
            "standard_rate_percent": str(VAT_STANDARD_RATE),
            "latest_ura_faq_threshold_ugx": str(VAT_THRESHOLD_LATEST_URA_FAQ),
            "other_official_page_threshold_ugx": str(VAT_THRESHOLD_OTHER_OFFICIAL_PAGE),
            "threshold_status": "CONFLICTING_PUBLIC_GUIDANCE_VERIFY_WITH_URA",
            "note": "The URA FAQ published 23 October 2026 says UGX 300 million; another public government page currently says UGX 250 million. LEXA does not infer or change VAT-registration status from turnover. Verify the current legal threshold with URA before relying on it.",
        },
        "presumptive_tax": {
            "annual_turnover_ceiling_ugx": str(PRESUMPTIVE_MAX_TURNOVER),
            "records_kept_bands": [
                {"lower_exclusive": "0", "upper_inclusive": "10000000", "formula": "Nil"},
                {"lower_exclusive": "10000000", "upper_inclusive": "30000000", "formula": "0.4% of turnover above UGX 10 million"},
                {"lower_exclusive": "30000000", "upper_inclusive": "50000000", "formula": "UGX 80,000 + 0.5% above UGX 30 million"},
                {"lower_exclusive": "50000000", "upper_inclusive": "80000000", "formula": "UGX 180,000 + 0.6% above UGX 50 million"},
                {"lower_exclusive": "80000000", "upper_inclusive": "150000000", "formula": "UGX 360,000 + 0.7% above UGX 80 million"},
            ],
            "without_records_fixed_amounts_ugx": ["0", "80000", "200000", "400000", "900000"],
            "excluded_sectors": sorted(EXCLUDED_PRESUMPTIVE_SECTORS),
        },
        "paye": {
            "frequency": "MONTHLY",
            "effective_from": "2026-07-01",
            "resident_individual_bands": [
                {"upper_inclusive": "335000", "formula": "Nil"},
                {"upper_inclusive": "410000", "formula": "20% of chargeable income above UGX 335,000"},
                {"upper_inclusive": "485000", "formula": "UGX 15,000 + 25% above UGX 410,000"},
                {"upper_inclusive": "10000000", "formula": "UGX 33,750 + 30% above UGX 485,000"},
                {"upper_inclusive": None, "formula": "UGX 33,750 + 30% above UGX 485,000 + 10% above UGX 10 million"},
            ],
            "non_resident_individual_bands": [
                {"upper_inclusive": "335000", "formula": "10% of chargeable income"},
                {"upper_inclusive": "410000", "formula": "UGX 33,500 + 20% above UGX 335,000"},
                {"upper_inclusive": None, "formula": "UGX 48,500 + 30% above UGX 410,000; add 10% above UGX 10 million"},
            ],
        },
        "withholding": {
            "taxable_supply_rate_percent": "6",
            "taxable_supply_threshold_ugx": "1000000",
            "resident_professional_management_rate_percent": "6",
            "non_resident_professional_management_rate_percent": "15",
            "condition": "The cited guidance describes duties for a business appointed as a withholding-tax agent.",
        },
        "sources": [
            {"publisher": "Uganda Revenue Authority", "published_on": "2026-10-23", "title": "Ask URA Commissioner General 41", "url": "https://ura.go.ug/en/ask-ura-commissioner-general-41/"},
            {"publisher": "Uganda Revenue Authority", "published_on": "2026-09-07", "title": "Changes to PAYE Return Form following the Income Tax (Amendment) Act, 2026", "url": "https://ura.go.ug/en/changes-to-paye-return-form-following-the-income-tax-amendment-act-2026/"},
            {"publisher": "Uganda Revenue Authority", "published_on": "2026-08-10", "title": "Additional taxpayers required to use EFRIS", "url": "https://ura.go.ug/en/additional-taxpayers-required-to-use-efris/"},
            {"publisher": "Government of Uganda", "published_on": "2026-06-15", "title": "VAT Registration — Licensing & Compliance", "url": "https://doingbusiness.finance.go.ug/licensing/ura-vat-registration"},
        ],
    }
