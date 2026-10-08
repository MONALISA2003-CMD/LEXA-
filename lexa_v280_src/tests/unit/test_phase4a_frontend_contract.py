from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "apps/web/app/commerce/page.tsx"


def test_commerce_page_covers_core_workflows():
    source = PAGE.read_text()
    for label in ("Sell", "Customers", "Payment Channels", "Receivables", "Reconciliation", "Returns", "Sales History"):
        assert f'"{label}"' in source
    for action in ("createCommerceSale", "createCommerceCustomer", "createPaymentChannel", "payReceivable", "createReconciliation", "setReconciliationActual", "resolveReconciliationLine", "closeReconciliation", "createSaleReturn"):
        assert action in source


def test_commerce_page_uses_local_business_date_and_no_credentials_ui():
    source = PAGE.read_text()
    assert 'getMonth() + 1' in source
    assert 'getDate()' in source
    assert "API key" in source
    assert "password" in source
    assert "OTP" in source
    assert "PIN" in source


def test_checkout_supports_split_payments_and_credit():
    source = PAGE.read_text()
    assert "paymentRows" in source
    assert "Add another payment" in source
    assert "customer_party_id: customerId || null" in source
    assert "payments," in source
