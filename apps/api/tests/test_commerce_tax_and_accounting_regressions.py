from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_checkout_resolves_tax_from_tenant_effective_dated_rules_and_persists_business_date():
    source = (ROOT / "apps/api/app/routes/commerce.py").read_text(encoding="utf-8")
    assert "public.resolve_tax_rate(:tenant_id,:product_id,:category_id,:business_date)" in source
    assert '"business_date":body.business_date' in source
    assert "s.business_date" in source
    assert "tax_rate_source" in source
    assert "INSERT INTO sales(tenant_id,transaction_id,customer_party_id,branch_id,location_id,business_date" in source


def test_new_migration_repairs_cogs_case_and_vat_exclusive_margin():
    migration = (ROOT / "migrations/041_commerce_integrity_scaling.sql").read_text(encoding="utf-8")
    assert "lower(reference_type)='sale'" in migration
    assert "transaction_type='SALE'" in migration
    assert "business_date BETWEEN p_from AND p_to" in migration
    assert "returns_tax_amount" in migration
    assert "(COALESCE(sl.sales_amount,0)-COALESCE(sl.tax_amount,0))" in migration


def test_efris_status_cannot_be_manually_declared_active_by_configuration_api():
    source = (ROOT / "apps/api/app/routes/finance.py").read_text(encoding="utf-8")
    config_contract = source.split("class EfrisConfigPatch", 1)[1].split("\n\n", 1)[0]
    assert "registration_status:" not in config_contract
    assert "registration_status=CASE WHEN EXCLUDED.integration_mode='MANUAL' THEN 'NOT_REGISTERED' ELSE 'PENDING' END" in source
    assert "verified, active EFRIS system-to-system connection" in (ROOT / "migrations/041_commerce_integrity_scaling.sql").read_text(encoding="utf-8")


def test_sale_payment_allocation_uses_the_sale_business_date_and_not_a_missing_payment_date_field():
    source = (ROOT / "apps/api/app/routes/commerce.py").read_text(encoding="utf-8")
    sale_block = source.split('@router.post("/sales", status_code=201)', 1)[1].split('@router.get("/receivables")', 1)[0]
    assert '"d":body.business_date' in sale_block
    assert '"d":payment.business_date' not in sale_block
    assert 'effective_from<=:business_date::timestamptz' in sale_block


def test_credit_note_requires_accepted_source_invoice_and_system_to_system_mode():
    sql = (ROOT / "migrations" / "041_commerce_integrity_scaling.sql").read_text()
    function = sql.split("CREATE OR REPLACE FUNCTION create_fiscal_document_for_return", 1)[1].split("CREATE OR REPLACE FUNCTION refresh_analytics", 1)[0]
    assert "COALESCE(v_mode,'MANUAL')<>'SYSTEM_TO_SYSTEM'" in function
    assert "document_type='INVOICE' AND status='ACCEPTED'" in function
    assert "source_fiscal_document_id" in function
    assert "'CREDIT_NOTE',v_currency,v_date,'PENDING'" in function
