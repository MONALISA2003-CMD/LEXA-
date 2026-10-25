from decimal import Decimal

import pytest

from app.purchasing_approval_rules import (
    PurchaseApprovalLimitError, effective_purchase_approval_limit,
    needs_governance_override_reason,
)


def test_manager_can_approve_within_currency_specific_cap():
    result = effective_purchase_approval_limit(
        role_names=["Manager"], currency_code="UGX", purchase_total="750000.00",
        policies={("Manager", "UGX"): "1000000.00"},
    )
    assert result == Decimal("1000000.00")


def test_manager_cannot_approve_above_cap():
    with pytest.raises(PurchaseApprovalLimitError) as error:
        effective_purchase_approval_limit(
            role_names=["Manager"], currency_code="UGX", purchase_total="1000000.01",
            policies={("Manager", "UGX"): "1000000.00"},
        )
    assert error.value.code == "PURCHASE_APPROVAL_LIMIT_EXCEEDED"


def test_missing_limit_fails_closed():
    with pytest.raises(PurchaseApprovalLimitError) as error:
        effective_purchase_approval_limit(
            role_names=["Manager"], currency_code="UGX", purchase_total="1",
            policies={},
        )
    assert error.value.code == "PURCHASE_APPROVAL_LIMIT_NOT_CONFIGURED"


def test_different_currency_policy_is_not_an_implicit_fx_conversion():
    with pytest.raises(PurchaseApprovalLimitError) as error:
        effective_purchase_approval_limit(
            role_names=["Manager"], currency_code="UGX", purchase_total="100",
            policies={("Manager", "USD"): "1000"},
        )
    assert error.value.code == "PURCHASE_APPROVAL_LIMIT_NOT_CONFIGURED"


def test_multiple_approval_roles_use_strictest_applicable_cap():
    with pytest.raises(PurchaseApprovalLimitError) as error:
        effective_purchase_approval_limit(
            role_names=["Manager", "Finance / Accounting"], currency_code="UGX", purchase_total="501",
            policies={("Manager", "UGX"): "1000", ("Finance / Accounting", "UGX"): "500"},
        )
    assert error.value.code == "PURCHASE_APPROVAL_LIMIT_EXCEEDED"


def test_owner_or_administrator_has_explicit_governance_override():
    assert effective_purchase_approval_limit(
        role_names=["Manager", "Administrator"], currency_code="UGX", purchase_total="999999999",
        policies={},
    ) is None


def test_invalid_negative_policy_and_purchase_totals_are_rejected():
    for kwargs in [
        dict(role_names=["Manager"], currency_code="UGX", purchase_total="10", policies={("Manager", "UGX"): "-1"}),
        dict(role_names=["Manager"], currency_code="UGX", purchase_total="-1", policies={("Manager", "UGX"): "10"}),
    ]:
        with pytest.raises(PurchaseApprovalLimitError):
            effective_purchase_approval_limit(**kwargs)


def test_governance_override_reason_is_required_above_highest_configured_cap():
    policies = {("Manager", "UGX"): "1000000.00", ("Finance / Accounting", "UGX"): "2500000.00"}
    assert not needs_governance_override_reason(
        role_names=["Owner"], currency_code="UGX", purchase_total="2500000.00", policies=policies,
    )
    assert needs_governance_override_reason(
        role_names=["Owner"], currency_code="UGX", purchase_total="2500000.01", policies=policies,
    )

def test_override_reason_is_not_required_when_no_cap_is_configured_for_that_currency():
    assert not needs_governance_override_reason(
        role_names=["Administrator"], currency_code="UGX", purchase_total="999999999",
        policies={("Manager", "USD"): "1"},
    )
