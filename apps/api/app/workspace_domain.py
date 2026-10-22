"""Pure helpers for Phase 3 workspace setup and membership access."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


def invitation_token_digest(token: str) -> str:
    """Hash a high-entropy invitation bearer token before persistence or lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def setup_progress(
    *,
    profile_exists: bool,
    branch_count: int,
    warehouse_count: int,
    location_count: int,
    payment_method_count: int = 0,
    accounting_account_count: int = 0,
    accounting_mapping_count: int = 0,
) -> dict[str, Any]:
    """Derive resumable setup from persisted records, never a shadow flag.

    The first four items make daily stock and sales operations possible. The last
    two ensure sales and expense records have a default way to record money and a
    usable chart of accounts before the owner is told setup is finished.
    """
    steps = [
        {"key": "business_profile", "label": "Business details", "href": "/administration", "required": True, "complete": profile_exists},
        {"key": "branch", "label": "Main branch", "href": "/administration", "required": True, "complete": branch_count > 0},
        {"key": "warehouse", "label": "Stock room", "href": "/administration", "required": True, "complete": warehouse_count > 0},
        {"key": "location", "label": "Where stock is kept", "href": "/administration", "required": True, "complete": location_count > 0},
        {"key": "payment_method", "label": "Payment method", "href": "/commerce", "required": True, "complete": payment_method_count > 0},
        {"key": "money_tracking", "label": "Money tracking", "href": "/accounting", "required": True, "complete": accounting_account_count > 0 and accounting_mapping_count > 0},
    ]
    first_incomplete = next((step for step in steps if step["required"] and not step["complete"]), None)
    completed = sum(1 for step in steps if step["complete"])
    return {
        "status": "COMPLETE" if first_incomplete is None else "IN_PROGRESS",
        "complete": first_incomplete is None,
        "completed_required_steps": completed,
        "required_steps": sum(1 for step in steps if step["required"]),
        "resume_path": first_incomplete["href"] if first_incomplete else "/",
        "steps": steps,
    }


def invitation_is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        # Naive timestamps are treated as UTC; DB columns are expected to be timestamptz.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= current


def normalize_branch_ids(branch_ids: list[str]) -> list[str]:
    """Return stable unique IDs without changing caller-provided identity values."""
    return list(dict.fromkeys(str(branch_id) for branch_id in branch_ids))
