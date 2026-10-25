from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_approval_limit_routes_are_scoped_and_database_repeats_the_limit_guard():
    route = (ROOT / "apps/api/app/routes/purchasing_approval.py").read_text(encoding="utf-8")
    rules = (ROOT / "apps/api/app/purchasing_approval_rules.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations/048_phase7_approval_limits_reversals_accounting.sql").read_text(encoding="utf-8")
    assert '@router.get("/approval-limits")' in route
    assert '@router.put("/approval-limits")' in route
    assert 'Depends(require_permission("purchasing.approval_limits.manage"))' in route
    assert "effective_purchase_approval_limit(" in route
    assert "PURCHASE_APPROVAL_LIMIT_NOT_CONFIGURED" in rules
    assert "PURCHASE_APPROVAL_LIMIT_EXCEEDED" in rules
    assert "needs_governance_override_reason(" in route
    assert "PURCHASE_APPROVAL_OVERRIDE_REASON_REQUIRED" in route
    assert "trg_purchase_order_approval_limit" in migration
    assert "PURCHASE_APPROVAL_LIMIT_EXCEEDED_OR_NOT_CONFIGURED" in migration
    assert "r.name IN ('Owner','Administrator','Admin')" in migration
    assert "purchase_approval_limits_tenant_isolation" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration and "FORCE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL PRIVILEGES ON FUNCTION" in migration
    assert "public.seed_purchasing_accounting_accounts(uuid)" in migration
    assert "FROM PUBLIC, lexa_app" in migration


def test_posted_supplier_return_reversal_is_idempotent_and_compensating_not_destructive():
    route = (ROOT / "apps/api/app/routes/purchasing_approval.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations/048_phase7_approval_limits_reversals_accounting.sql").read_text(encoding="utf-8")
    assert '@router.post("/returns/{return_id}/reverse")' in route
    assert 'Depends(require_permission("purchasing.returns.reverse"))' in route
    assert '"IDEMPOTENCY_KEY_REQUIRED"' in route
    assert "status='REVERSED'" in route
    assert 'transaction_type="PURCHASE_RETURN_REVERSAL"' in route
    assert "reverses_transaction_id" in route
    assert "entry_type='RETURN_REVERSAL'" in route
    assert "reverse_journal_entry(v_original,v_user,current_date)" in migration
    assert "RETURN_REVERSAL" in migration
    assert "REVERSED" in migration
    assert "REVOKE ALL PRIVILEGES" in migration


def test_receipts_and_supplier_ledger_events_post_balanced_gl_journals_in_same_transaction():
    migration = (ROOT / "migrations/048_phase7_approval_limits_reversals_accounting.sql").read_text(encoding="utf-8")
    route = (ROOT / "apps/api/app/routes/purchasing_approval.py").read_text(encoding="utf-8")
    assert "post_purchase_receipt_journal" in migration
    assert "trg_purchasing_receipt_after_post" in migration
    assert "post_supplier_ledger_journal" in migration
    assert "trg_purchasing_supplier_ledger_after_insert" in migration
    assert "GOODS_RECEIVED_NOT_INVOICED" in migration
    assert "LANDED_COST_CLEARING" in migration
    assert "PURCHASES_CLEARING" in migration
    assert "SUPPLIER_ADVANCES" in migration
    assert "PURCHASE_COST_VARIANCE" in migration
    assert "PERFORM public.post_journal_entry(v_entry,v_user)" in migration
    assert "purchasing_reconciliation" in route


def test_reconciliation_reports_stock_ledger_supplier_gl_and_missing_or_unbalanced_journals():
    route = (ROOT / "apps/api/app/routes/purchasing_approval.py").read_text(encoding="utf-8")
    assert '@router.get("/reconciliation")' in route
    for key in [
        "stock_balance_ledger_mismatches", "posted_receipts_missing_journals",
        "supplier_ledger_entries_missing_journals", "unbalanced_posted_journals",
        "supplier_subledger_gl_mismatches", "purchase_inventory_value_difference",
    ]:
        assert key in route
    assert "require_full_branch_scope" in route
    assert '"read_only": True' in route
    assert "no cross-currency netting" in route


def test_schema_migration_is_forward_only_and_posts_existing_phase7_data_once():
    migration = (ROOT / "migrations/048_phase7_approval_limits_reversals_accounting.sql").read_text(encoding="utf-8")
    assert migration.strip().startswith("-- Phase 7 closeout")
    assert migration.strip().endswith("COMMIT;")
    assert "ON CONFLICT(tenant_id,source_id,entry_role)" not in migration  # journal uniqueness is delegated to the canonical source index
    assert "FOR r IN SELECT id FROM public.purchase_receipts WHERE status='POSTED'" in migration
    assert "FOR r IN SELECT id FROM public.supplier_ledger_entries WHERE entry_type IN ('BILL','PAYMENT','RETURN_CREDIT')" in migration
    assert "schema_migrations(version) VALUES ('048_phase7_approval_limits_reversals_accounting')" in migration


def test_readiness_fails_closed_until_phase7_schema_and_accounting_triggers_exist():
    main = (ROOT / "apps/api/app/main.py").read_text(encoding="utf-8")
    gate = (ROOT / "apps/api/app/phase7_release_gate.py").read_text(encoding="utf-8")
    assert "check_phase7_release_schema()" in main
    assert "048_phase7_approval_limits_reversals_accounting" in gate
    assert "purchase_approval_limits_tenant_isolation" in gate
    assert "trg_purchasing_receipt_after_post" in gate
    assert "trg_purchasing_supplier_ledger_after_insert" in gate
    assert "to_regprocedure('public.post_supplier_ledger_journal(uuid)')" in gate
