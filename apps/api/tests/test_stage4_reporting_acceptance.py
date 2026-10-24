import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _function_block(source: str, function_name: str) -> str:
    start = source.index(f"def {function_name}(")
    end = source.find("\n@router.", start)
    return source[start : end if end >= 0 else len(source)]


def test_sales_history_payment_method_drillthrough_is_bound_and_branch_scoped():
    commerce = _source("app/routes/commerce.py")
    block = _function_block(commerce, "list_sales")
    assert "payment_channel_id: UUID | None = None" in block
    assert "EXISTS (SELECT 1 FROM payments payment_filter" in block
    assert "payment_filter.status='RECORDED'" in block
    assert "payment_filter.payment_channel_id=:payment_channel_id" in block
    assert "membership_branch_assignments" in block
    assert "s.branch_id=:branch_id" in block


def test_report_aggregates_do_not_mix_currency_or_unrecorded_customer_payments():
    analytics = _source("app/routes/analytics.py")
    block = _function_block(analytics, "payments_by_channel")
    assert "require_full_branch_scope" in block
    assert "p.status = 'RECORDED'" in block
    assert "s.status = 'COMPLETED'" in block
    assert "p.currency_code = :currency_code" in block
    assert "p.business_date BETWEEN :start_date AND :end_date" in block


def test_expenses_by_category_are_built_from_posted_records_in_selected_window():
    reports = _source("../web/app/reports/page.tsx")
    assert 'row.status === "POSTED"' in reports
    assert "row.currency_code === currencyCode" in reports
    assert "row.expense_date >= (appliedRange?.from || from)" in reports
    assert "row.expense_date <= (appliedRange?.to || to)" in reports


def test_stage_5_browser_acceptance_is_read_only_and_gated_to_qa_storage_state():
    suite = _source("../web/e2e/phase8-reports-acceptance.spec.ts")
    assert "LEXA_PHASE8_STORAGE_STATE" in suite
    assert "test.skip" in suite
    assert "Download report (CSV)" in suite
    assert "test.setTimeout" not in suite
    assert "POST" not in suite.upper()


def test_stock_value_by_location_uses_complete_latest_snapshot_and_assigned_branch_scope():
    analytics = _source("app/routes/analytics.py")
    block = _function_block(analytics, "inventory_value_by_location")
    assert "MAX(latest.snapshot_date)" in block
    assert "SUM(a.stock_value)" in block
    assert "COUNT(DISTINCT a.variant_id)" in block
    assert "membership_branch_assignments" in block
    assert "tm.user_id = :actor_id" in block
    assert "a.snapshot_date = (" in block


def test_stage5_clean_replay_includes_phase8_migration_and_postconditions():
    manifest = json.loads(_source("../../migrations/reconstructed/clean_replay_order.json"))
    paths = [step["path"] for step in manifest["steps"]]
    replay = _source("../../scripts/run_clean_migration_replay.py")

    # Keep assertions about historical migration order independent of later,
    # forward-only additions to the canonical replay sequence.
    path_042 = "migrations/042_team_chat_foundation.sql"
    path_043 = "migrations/043_phase5_journal_currency_guard.sql"
    path_044 = "migrations/044_phase3_password_reset_security.sql"
    path_045 = "migrations/045_intelligence_foundation.sql"
    path_046 = "migrations/046_intelligence_documents.sql"
    assert path_042 in paths and path_043 in paths and path_044 in paths
    assert paths.index(path_042) < paths.index(path_043) < paths.index(path_044)
    assert paths.index(path_044) < paths.index(path_045) < paths.index(path_046)
    assert "040_phase8_finance_workflows" in replay
    assert "phase8_expense_posting_function" in replay
    assert "phase8_expense_reversal_reporting_metric" in replay
    assert "phase8_expense_reversal_tenant_safe_fk" in replay
    assert "phase8_expense_correction_status" in replay
    assert "host must be loopback" in replay
    assert "LEXA_ALLOW_DISPOSABLE_REPLAY" in replay
