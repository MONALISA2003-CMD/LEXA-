"""Regression tests for explicit currency handling across checkout and purchasing."""
from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ROOT = Path(__file__).resolve().parents[3]
COMMERCE = ROOT / "apps" / "api" / "app" / "routes" / "commerce.py"
PURCHASING = ROOT / "apps" / "api" / "app" / "routes" / "purchasing.py"
ORGANIZATION = ROOT / "apps" / "api" / "app" / "routes" / "organization.py"
FINANCE = ROOT / "apps" / "api" / "app" / "routes" / "finance.py"
JOURNAL_GUARD = ROOT / "migrations" / "043_phase5_journal_currency_guard.sql"


def _models_from_commerce():
    tree = ast.parse(COMMERCE.read_text())
    wanted = {"Strict", "SaleLineIn", "PaymentAllocationIn", "SaleCreate"}
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    namespace = {
        "BaseModel": BaseModel,
        "ConfigDict": ConfigDict,
        "Field": Field,
        "field_validator": field_validator,
        "Decimal": Decimal,
        "UUID": UUID,
        "date": date,
        "safe_payment_reference": lambda value: value,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(COMMERCE), "exec"), namespace)
    for name in ("Strict", "SaleLineIn", "PaymentAllocationIn", "SaleCreate"):
        namespace[name].model_rebuild(_types_namespace=namespace)
    return namespace["SaleCreate"]


def test_checkout_currency_is_normalized_and_must_be_three_letters():
    SaleCreate = _models_from_commerce()
    good = SaleCreate(currency_code=" ugx ", lines=[{
        "variant_id": "20000000-0000-4000-8000-000000000001",
        "quantity": "1", "unit_price": "1000",
    }])
    assert good.currency_code == "UGX"
    with pytest.raises(ValidationError):
        SaleCreate(currency_code="U$X", lines=[{
            "variant_id": "20000000-0000-4000-8000-000000000001",
            "quantity": "1", "unit_price": "1000",
        }])


def test_checkout_and_dashboard_require_saved_business_currency_without_ugx_fallback():
    source = COMMERCE.read_text()
    assert "def require_business_currency(" in source
    assert "if not re.fullmatch(r\"[A-Z]{3}\", currency):" in source
    assert "Set a valid business currency in Settings" in source
    assert "if body.currency_code != currency:" in source
    assert "def default_currency(" not in source
    assert 'scalar_one_or_none() or "UGX"' not in source


def test_currency_fields_are_explicit_for_supplier_bill_payment_and_cost_writes():
    source = PURCHASING.read_text()
    tree = ast.parse(source)
    required = {"SupplierCreate", "SupplierCostCreate", "SupplierBillCreate", "SupplierPaymentCreate"}
    fields = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in required:
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "currency_code":
                    fields[node.name] = item.value
    assert set(fields) == required
    # Explicit currencies may have a validator/pattern, but may not default to UGX.
    for model_name, value in fields.items():
        assert "default" not in ast.dump(value), f"{model_name} silently defaults its currency"
        assert "A-Za-z" in ast.unparse(value) and "3" in ast.unparse(value), model_name


def test_purchasing_frontend_never_sends_implicit_ugx_for_supplier_operations():
    source = (ROOT / "apps" / "web" / "app" / "purchasing" / "page.tsx").read_text()
    assert 'useState("UGX")' not in source
    assert 'supplierMap.get(poSupplier)?.currency_code || businessCurrency || "UGX"' not in source
    assert 'supplierMap.get(billSupplier)?.currency_code || businessCurrency || "UGX"' not in source
    assert 'supplierMap.get(paymentSupplier)?.currency_code || businessCurrency || "UGX"' not in source
    assert "const supplierCurrencyFor = (id: string): string | null" in source
    assert "Correct the supplier profile before recording a payment." in source


def test_business_currency_is_locked_after_any_recorded_money_or_stock_activity():
    source = ORGANIZATION.read_text()
    assert "def _has_financial_activity(" in source
    assert '"journal_entries"' in source and '"inventory_transactions"' in source and '"sales"' in source
    assert '"supplier_variant_costs"' in source and '"purchase_landed_costs"' in source and '"payment_allocations"' in source
    assert 'if "currency_code" in updates' in source
    assert "Business currency is locked after sales, stock movements, purchases, expenses or journal activity" in source


def test_purchasing_and_expenses_reject_unconverted_foreign_currency():
    purchasing = PURCHASING.read_text()
    finance = FINANCE.read_text()
    assert "def _require_business_currency(" in purchasing
    for marker in ("def set_supplier_cost(", "def create_purchase_order(", "def post_receipt(", "def create_supplier_bill(", "def post_supplier_bill(", "def create_supplier_payment(", "def post_supplier_payment("):
        block = purchasing[purchasing.index(marker):]
        assert "_require_business_currency(" in block[:12000], marker
    assert "Foreign-currency expenses are not enabled" in finance
    assert "body.currency_code != business_currency" in finance


def test_journal_posting_guard_requires_single_currency_and_balanced_lines():
    sql = JOURNAL_GUARD.read_text()
    assert "upper(jl.currency_code) <> v_currency" in sql
    assert "a.currency_code IS NOT NULL AND upper(a.currency_code) <> v_currency" in sql
    assert "round(v_debit, 4) <> round(v_credit, 4)" in sql
    assert "Only draft journal entries can be posted" in sql
    assert "043_phase5_journal_currency_guard" in sql
    replay = (ROOT / "scripts" / "run_clean_migration_replay.py").read_text()
    verifier = (ROOT / "scripts" / "check_phase6_replay_evidence.py").read_text()
    assert "journal_entry_currency_guard" in replay and "journal_entry_currency_guard" in verifier
    assert "GRANT EXECUTE ON FUNCTION public.post_journal_entry(uuid, uuid) TO lexa_app" in sql
    assert "journal_posting_grant" in replay and "journal_posting_grant" in verifier
