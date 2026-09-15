"""Pure Catalog domain validation helpers; deliberately DB-independent."""
from __future__ import annotations

from decimal import Decimal
from typing import Any


class CatalogValidation(ValueError):
    """A Catalog business rule or input invariant was violated."""


def normalize_code(value: str, field: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise CatalogValidation(f"{field} cannot be empty")
    return normalized


def normalize_text(value: str, field: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise CatalogValidation(f"{field} cannot be empty")
    return normalized


def validate_price(value: Any) -> None:
    if value is None or Decimal(value) < 0:
        raise CatalogValidation("Price must be zero or greater")


def validate_minimum_quantity(value: Any) -> None:
    if value is None or Decimal(value) <= 0:
        raise CatalogValidation("Minimum quantity must be greater than zero")
