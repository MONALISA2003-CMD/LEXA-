"""Pure Phase 7 purchasing approval-limit policy.

Owner/Administrator roles have an explicit governance override. Other approvers
must have an approved per-role, per-currency cap; the strictest applicable cap
wins when a member has more than one eligible role. No FX conversion is implied.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Iterable


class PurchaseApprovalLimitError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def effective_purchase_approval_limit(
    *,
    role_names: Iterable[str],
    currency_code: str,
    purchase_total: Decimal | str | int,
    policies: Mapping[tuple[str, str], Decimal | str | int],
) -> Decimal | None:
    """Validate an approval and return the applied limit; ``None`` means override.

    A policy must exist for every non-privileged role that grants purchasing.approve.
    A policy for a different currency is not interchangeable. Limits are compared
    using Decimal to avoid floating-point approval bypasses.
    """
    roles = {str(role).strip() for role in role_names if str(role).strip()}
    if roles.intersection({"Owner", "Administrator", "Admin"}):
        return None
    eligible = sorted(roles)
    if not eligible:
        raise PurchaseApprovalLimitError(
            "PURCHASE_APPROVER_ROLE_REQUIRED",
            "An active role with purchasing approval permission is required.",
        )
    currency = str(currency_code).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise PurchaseApprovalLimitError(
            "PURCHASE_APPROVAL_CURRENCY_INVALID", "A valid three-letter currency is required."
        )
    caps: list[Decimal] = []
    for role in eligible:
        raw_cap = policies.get((role, currency))
        if raw_cap is None:
            raise PurchaseApprovalLimitError(
                "PURCHASE_APPROVAL_LIMIT_NOT_CONFIGURED",
                f"No {currency} purchase-approval limit is configured for the {role} role.",
            )
        cap = Decimal(str(raw_cap))
        if not cap.is_finite() or cap < 0:
            raise PurchaseApprovalLimitError(
                "PURCHASE_APPROVAL_POLICY_INVALID", "The configured purchase-approval limit is invalid."
            )
        caps.append(cap)
    effective = min(caps)
    amount = Decimal(str(purchase_total))
    if not amount.is_finite() or amount < 0:
        raise PurchaseApprovalLimitError(
            "PURCHASE_APPROVAL_AMOUNT_INVALID", "The purchase-order total is invalid."
        )
    if amount > effective:
        raise PurchaseApprovalLimitError(
            "PURCHASE_APPROVAL_LIMIT_EXCEEDED",
            f"This purchase order exceeds your {currency} approval limit of {effective}.",
        )
    return effective


def needs_governance_override_reason(
    *,
    role_names: Iterable[str],
    currency_code: str,
    purchase_total: Decimal | str | int,
    policies: Mapping[tuple[str, str], Decimal | str | int],
) -> bool:
    """Require a reason when a privileged approver exceeds every configured cap.

    Owner/Administrator remain explicit override roles, but the override becomes
    auditable when it exceeds the highest cap configured for that currency. If no
    limits exist yet, there is no policy threshold to override.
    """
    privileged = {"owner", "administrator", "admin"}
    roles = {str(role).strip().casefold() for role in role_names if str(role).strip()}
    if not roles.intersection(privileged):
        return False
    currency = str(currency_code).strip().upper()
    amount = Decimal(str(purchase_total))
    if not amount.is_finite() or amount < 0:
        raise PurchaseApprovalLimitError(
            "PURCHASE_APPROVAL_AMOUNT_INVALID", "The purchase-order total is invalid."
        )
    caps = [
        Decimal(str(cap))
        for (role_name, code), cap in policies.items()
        if str(code).strip().upper() == currency
        and str(role_name).strip().casefold() not in privileged
    ]
    if any(not cap.is_finite() or cap < 0 for cap in caps):
        raise PurchaseApprovalLimitError(
            "PURCHASE_APPROVAL_POLICY_INVALID", "The configured purchase-approval limit is invalid."
        )
    return bool(caps) and amount > max(caps)
