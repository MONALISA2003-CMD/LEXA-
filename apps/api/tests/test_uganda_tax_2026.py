from decimal import Decimal

import pytest

from app.uganda_tax_2026 import (
    calculate_paye,
    calculate_presumptive_tax,
    calculate_vat,
    calculate_withholding,
    tax_reference_payload,
)


def test_vat_exclusive_and_inclusive_are_rounded_with_decimal_arithmetic():
    exclusive = calculate_vat("100.00")
    assert exclusive["tax_amount"] == "18.00"
    assert exclusive["total_amount"] == "118.00"
    inclusive = calculate_vat("118.00", price_includes_tax=True)
    assert inclusive["taxable_base"] == "100.00"
    assert inclusive["tax_amount"] == "18.00"
    assert inclusive["total_amount"] == "118.00"


def test_presumptive_tax_bands_and_recordkeeping_rules():
    with_records = calculate_presumptive_tax("40000000", records_kept=True)
    without_records = calculate_presumptive_tax("40000000", records_kept=False)
    assert with_records["tax_amount"] == "130000.00"
    assert without_records["tax_amount"] == "200000.00"
    assert calculate_presumptive_tax("10000000", records_kept=True)["tax_amount"] == "0.00"


def test_presumptive_estimate_fails_closed_when_eligibility_is_not_met():
    assert calculate_presumptive_tax("30000000", records_kept=True, resident_taxpayer=False)["eligible"] is False
    assert calculate_presumptive_tax("30000000", records_kept=True, sector="ACCOUNTING")["eligible"] is False
    assert calculate_presumptive_tax("150000001", records_kept=True)["eligible"] is False


def test_resident_paye_uses_july_2026_bands():
    result = calculate_paye("500000", residency="RESIDENT")
    assert result["tax_amount"] == "38250.00"
    assert result["tax_type"] == "RESIDENT_MONTHLY_PAYE"


def test_nonresident_paye_uses_separate_published_bands():
    assert calculate_paye("300000", residency="NON_RESIDENT")["tax_amount"] == "30000.00"
    result = calculate_paye("500000", residency="NON_RESIDENT")
    assert result["tax_amount"] == "75500.00"
    assert result["tax_type"] == "NON_RESIDENT_MONTHLY_PAYE"


def test_wht_requires_confirmed_agent_status_and_threshold_condition():
    not_agent = calculate_withholding("2500000", withholding_agent=False, withholding_kind="TAXABLE_SUPPLY")
    assert not_agent["eligible"] is False
    at_threshold = calculate_withholding("1000000", withholding_agent=True, withholding_kind="TAXABLE_SUPPLY")
    assert at_threshold["tax_amount"] == "0.00"
    above_threshold = calculate_withholding("1000001", withholding_agent=True, withholding_kind="TAXABLE_SUPPLY")
    assert above_threshold["tax_amount"] == "60000.06"
    professional = calculate_withholding("1000000", withholding_agent=True, withholding_kind="PROFESSIONAL_OR_MANAGEMENT", payee_residency="NON_RESIDENT")
    assert professional["tax_amount"] == "150000.00"


def test_estimates_reject_invalid_or_nonfinite_values():
    with pytest.raises(ValueError):
        calculate_vat("NaN")
    with pytest.raises(ValueError):
        calculate_vat("-1")
    with pytest.raises(ValueError):
        calculate_paye("500000", residency="SOME_OTHER_STATUS")


def test_tax_reference_discloses_official_vat_threshold_conflict_and_no_provider_calls():
    payload = tax_reference_payload()
    assert payload["reference_date"] == "2026-10-23"
    assert payload["provider_integrations"] is False
    assert payload["payment_handling"] == "RECORD_ONLY"
    assert payload["efris_mode"] == "MANUAL_RECORD_ONLY"
    assert payload["vat"]["latest_ura_faq_threshold_ugx"] == "300000000"
    assert payload["vat"]["other_official_page_threshold_ugx"] == "250000000"
    assert payload["vat"]["threshold_status"] == "CONFLICTING_PUBLIC_GUIDANCE_VERIFY_WITH_URA"


def test_all_presumptive_bands_have_the_published_fixed_and_records_amounts():
    records_cases = [
        ("20000000", "40000.00"),
        ("40000000", "130000.00"),
        ("60000000", "240000.00"),
        ("100000000", "500000.00"),
        ("150000000", "850000.00"),
    ]
    fixed_cases = [
        ("20000000", "80000.00"),
        ("40000000", "200000.00"),
        ("60000000", "400000.00"),
        ("100000000", "900000.00"),
        ("150000000", "900000.00"),
    ]
    for turnover, expected in records_cases:
        assert calculate_presumptive_tax(turnover, records_kept=True)["tax_amount"] == expected
    for turnover, expected in fixed_cases:
        assert calculate_presumptive_tax(turnover, records_kept=False)["tax_amount"] == expected


def test_paye_top_band_adds_ten_percent_only_above_ten_million():
    resident = calculate_paye("11000000", residency="RESIDENT")
    nonresident = calculate_paye("11000000", residency="NON_RESIDENT")
    assert resident["tax_amount"] == "3288250.00"
    assert nonresident["tax_amount"] == "3325500.00"


def test_very_large_amount_fails_as_validation_error_not_decimal_overflow():
    with pytest.raises(ValueError):
        calculate_vat("9" * 1000)
