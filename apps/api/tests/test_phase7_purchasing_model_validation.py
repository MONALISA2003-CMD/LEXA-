"""Runtime regressions for Phase 7 supplier payment request validation.

The test executes the literal request-model class definitions from purchasing.py
in isolation so it remains runnable in offline analysis environments lacking the
PostgreSQL driver. CI still imports the full API through the regular test suite.
"""
import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.purchasing_rules import validate_payment_allocations


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps" / "api" / "app" / "routes" / "purchasing.py"
TREE = ast.parse(SOURCE.read_text())
NEEDED = {"Strict", "PaymentAllocationIn", "SupplierPaymentCreate"}
DEFINITIONS = [node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name in NEEDED]
assert {node.name for node in DEFINITIONS} == NEEDED
assert sum(1 for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "SupplierPaymentCreate") == 1

MODEL_NAMESPACE = {
    "BaseModel": BaseModel,
    "ConfigDict": ConfigDict,
    "Field": Field,
    "ValidationError": ValidationError,
    "field_validator": field_validator,
    "model_validator": model_validator,
    "Decimal": Decimal,
    "UUID": UUID,
    "date": date,
    "ZERO": Decimal("0"),
    "validate_payment_allocations": validate_payment_allocations,
}
# Guard against the original production bug: the shared validator must really be
# imported by purchasing.py, not just injected into this isolated execution.
IMPORTS_SHARED_RULE = any(
    isinstance(node, ast.ImportFrom)
    and node.level == 2
    and node.module == "purchasing_rules"
    and any(alias.name == "validate_payment_allocations" for alias in node.names)
    for node in TREE.body
)
assert IMPORTS_SHARED_RULE, "purchasing.py must import validate_payment_allocations"
exec(compile(ast.Module(body=DEFINITIONS, type_ignores=[]), str(SOURCE), "exec"), MODEL_NAMESPACE)
SupplierPaymentCreate = MODEL_NAMESPACE["SupplierPaymentCreate"]


SUPPLIER_ID = UUID("20000000-0000-4000-8000-000000000001")
BILL_A = UUID("30000000-0000-4000-8000-000000000001")
BILL_B = UUID("30000000-0000-4000-8000-000000000002")


def payment(*, amount="100.00", allocations=None, currency="ugx"):
    return SupplierPaymentCreate(
        supplier_party_id=SUPPLIER_ID,
        payment_number="P7-VALIDATION-001",
        currency_code=currency,
        amount=amount,
        payment_method="BANK_TRANSFER",
        allocations=allocations or [],
    )


def test_supplier_payment_model_runs_shared_validation_and_normalizes_currency():
    assert payment().currency_code == "UGX"
    valid = payment(allocations=[{"bill_id": str(BILL_A), "amount": "30.00"}, {"bill_id": str(BILL_B), "amount": "20.00"}])
    assert len(valid.allocations) == 2


def test_supplier_payment_requires_explicit_currency():
    with pytest.raises(ValidationError):
        SupplierPaymentCreate(
            supplier_party_id=SUPPLIER_ID,
            payment_number="P7-NO-CURRENCY",
            amount="10.00",
            payment_method="BANK_TRANSFER",
        )


def test_supplier_payment_model_rejects_duplicate_bill_allocations():
    with pytest.raises(ValidationError, match="allocate to each bill only once"):
        payment(allocations=[{"bill_id": str(BILL_A), "amount": "20.00"}, {"bill_id": str(BILL_A), "amount": "10.00"}])


def test_supplier_payment_model_rejects_allocations_above_payment_amount():
    with pytest.raises(ValidationError, match="cannot exceed payment amount"):
        payment(amount="100.00", allocations=[{"bill_id": str(BILL_A), "amount": "101.00"}])
