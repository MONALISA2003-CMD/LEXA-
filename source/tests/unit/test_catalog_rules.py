from decimal import Decimal

import pytest

from apps.api.app.catalog_rules import CatalogValidation, normalize_code, normalize_text, validate_minimum_quantity, validate_price


def test_normalize_code():
    assert normalize_code("  abc-123 ", "SKU") == "ABC-123"


def test_empty_text_rejected():
    with pytest.raises(CatalogValidation):
        normalize_text("   ", "Product name")


def test_negative_price_rejected():
    with pytest.raises(CatalogValidation):
        validate_price(Decimal("-1"))


def test_zero_minimum_quantity_rejected():
    with pytest.raises(CatalogValidation):
        validate_minimum_quantity(Decimal("0"))


def test_request_hash_is_order_independent():
    from apps.api.app.catalog_rules import request_hash

    assert request_hash({"b": 2, "a": 1}) == request_hash({"a": 1, "b": 2})
