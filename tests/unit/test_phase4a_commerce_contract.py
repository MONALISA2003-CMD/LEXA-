from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "apps/api/app/routes/commerce.py"
API = ROOT / "apps/web/lib/api.ts"
PAGE = ROOT / "apps/web/app/commerce/page.tsx"
MAIN = ROOT / "apps/api/app/main.py"
MIG = ROOT / "migrations/018_phase4a_application_integrity.sql"


def test_commerce_router_is_registered_and_protected():
    route = ROUTE.read_text()
    main = MAIN.read_text()
    assert 'router = APIRouter(prefix="/commerce"' in route
    assert 'app.include_router(commerce.router, prefix="/api/v1")' in main
    for permission in (
        "sales.read", "sales.complete", "sales.return", "customers.read", "customers.manage",
        "payments.read", "financial.configure", "payments.allocate", "receivables.read",
        "reconciliation.read", "reconciliation.manage", "reconciliation.resolve", "reconciliation.close",
    ):
        assert f'require_permission("{permission}")' in route


def test_commerce_sale_path_preserves_core_invariants():
    route = ROUTE.read_text()
    assert "post_ledger(" in route
    assert "transaction_type=\"SALE\"" in route
    assert "INSERT INTO payment_allocations" in route
    assert "INSERT INTO receivables" in route
    assert "SALE_COMPLETED" in route
    assert "Idempotency-Key" in route
    assert "Payment allocations cannot exceed sale total" in route
    assert "A customer is required for credit/outstanding sales" in route


def test_payment_channel_contract_forbids_credentials():
    route = ROUTE.read_text()
    assert "account_number" not in route
    assert "api_key" not in route
    assert "access_token" not in route
    import re
    lower = route.lower()
    assert re.search(r"\bpin\b", lower) is None
    assert re.search(r"\botp\b", lower) is None
    assert re.search(r"\bpassword\b", lower) is None
    assert "CHANNEL_TYPES = {\"CASH\", \"MOBILE_MONEY\", \"BANK\", \"CARD\", \"CHEQUE\", \"OTHER\"}" in route


def test_reconciliation_and_return_paths_are_exposed():
    route = ROUTE.read_text()
    expected = [
        'get("/reconciliations")',
        'post("/reconciliations"',
        'post("/reconciliation-lines/{line_id}/actual")',
        'post("/reconciliation-lines/{line_id}/resolve")',
        'post("/reconciliations/{reconciliation_id}/close")',
        'get("/returns")',
        'post("/sales/{sale_id}/returns"',
        'get("/sales/{sale_id}")',
    ]
    for marker in expected:
        assert marker in route
    assert "return_adjustment_amount=return_adjustment_amount+:a" in route
    assert "SET adjustment_amount=LEAST" in route


def test_frontend_calls_same_commerce_contracts():
    api = API.read_text()
    page = PAGE.read_text()
    for marker in (
        "/api/v1/commerce/dashboard", "/api/v1/commerce/customers", "/api/v1/commerce/payment-channels",
        "/api/v1/commerce/products", "/api/v1/commerce/sales", "/api/v1/commerce/receivables",
        "/api/v1/commerce/reconciliations", "/api/v1/commerce/reconciliation-lines/", "/api/v1/commerce/returns",
    ):
        assert marker in api
    for name in (
        "getCommerceDashboard", "getCommerceCustomers", "getPaymentChannels", "getCommerceProducts",
        "getCommerceSales", "getCommerceSale", "getReceivables", "payReceivable", "getReconciliations",
        "createReconciliation", "setReconciliationActual", "resolveReconciliationLine", "closeReconciliation",
        "getSaleReturns", "createSaleReturn",
    ):
        assert re.search(rf"export function {name}\b", api)
        assert name in page


def test_018_source_contains_the_live_integrity_guards():
    mig = MIG.read_text()
    assert "CREATE OR REPLACE FUNCTION refresh_receivable" in mig
    assert "Payment facts are immutable" in mig or "Recorded payment facts are immutable" in mig
    assert "Closed reconciliations cannot be edited" in mig
    assert "trg_refresh_reconciliation_header_after_line" in mig
    assert "UPDATE payment_allocations" in mig
    assert "status='REVERSED'" in mig


def test_credit_limit_and_customer_credit_contracts():
    route = ROUTE.read_text()
    api = API.read_text()
    page = PAGE.read_text()
    assert "available_credit" in route
    assert "available credit" in route.lower()
    assert 'reference_type="sale"' in route
    assert "get(\"/customer-credits\")" in route
    assert 'post("/customer-credits/{credit_id}/allocate"' in route
    assert "getCustomerCredits" in api
    assert "allocateCustomerCredit" in api
    assert "Customer Credits" in page


def test_reconciliation_mutations_are_idempotent():
    route = ROUTE.read_text()
    api = API.read_text()
    assert "commerce.reconciliation.actual" in route
    assert "commerce.reconciliation.resolve" in route
    assert "commerce.reconciliation.close" in route
    assert "Idempotency-Key" in api


def test_019_customer_credit_migration_present():
    mig = ROOT / "migrations/019_phase4a_customer_credit_allocation.sql"
    source = mig.read_text()
    for marker in ("refresh_customer_credit", "customer_credit_allocations", "validate_customer_credit_allocation", "refresh_receivable"):
        assert marker in source


def test_sidebar_uses_bounded_brand_asset():
    page = (ROOT / "apps/web/app/page.tsx").read_text()
    css = (ROOT / "apps/web/app/globals.css").read_text()
    assert 'src="/lexa-icon.png"' in page
    assert ".lexa-sidebar-mark" in css
    assert "overflow:hidden" in css
