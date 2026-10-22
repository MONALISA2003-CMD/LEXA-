from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_inventory_ageing_is_tenant_and_location_scoped_and_labels_unknown_provenance():
    route = (ROOT / "apps/api/app/routes/inventory.py").read_text()
    migration = (ROOT / "migrations/037_phase6_inventory_ageing_index.sql").read_text()
    assert '@router.get("/ageing")' in route
    assert 'require_permission("inventory.read")' in route
    assert 'accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)' in route
    assert 'ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)' in route
    assert "unknown_age_quantity" in route
    assert "aged_over_30" in route and "aged_over_60" in route and "aged_over_90" in route
    assert "reconciliation_gap" in route
    assert "idx_inventory_transactions_age_analysis" in migration
    assert "INSERT INTO public.schema_migrations" in migration


def test_clean_replay_contains_ageing_migration_and_evidence_gate_checks_it():
    order = json.loads((ROOT / "migrations/reconstructed/clean_replay_order.json").read_text())
    assert order["steps"][-4]["path"] == "migrations/039_phase7_supplier_ledger_landed_costs.sql"
    assert order["steps"][-3]["path"] == "migrations/040_phase8_finance_workflows.sql"
    assert order["steps"][-2]["path"] == "migrations/041_commerce_integrity_scaling.sql"
    assert order["steps"][-1]["path"] == "migrations/042_team_chat_foundation.sql"
    assert len(order["steps"]) == 46
    replay = (ROOT / "scripts/run_clean_migration_replay.py").read_text()
    verifier = (ROOT / "scripts/check_phase6_replay_evidence.py").read_text()
    assert "037_phase6_inventory_ageing_index" in replay
    assert "idx_inventory_transactions_age_analysis" in replay
    assert "phase6_inventory_age_index_count" in verifier
    assert "phase6_inventory_health_index_count" in verifier
    assert "phase8_expense_reversal_reference" in verifier
    assert "phase8_expense_posting_routine" in verifier
    assert "phase8_expense_reversal_tenant_safe_fk" in verifier


def test_phase3_six_lost_sources_remain_permanently_dispositioned_not_reopened():
    dispositions = json.loads((ROOT / "migrations/migration_dispositions.json").read_text())
    gaps = json.loads((ROOT / "migrations/source_gaps.json").read_text())
    assert dispositions["historical_recovery_gate"] == "CLOSED_BY_PERMANENT_DISPOSITION"
    assert len(dispositions["permanently_replaced_sources"]) == 6
    assert all(row["disposition"] == "PERMANENTLY_REPLACED" for row in gaps["gaps"])
    assert all(row["recovery_status"] == "CLOSED_NO_FURTHER_SEARCH" for row in gaps["gaps"])


def test_phase6_movement_health_is_location_scoped_and_reports_sales_returns_separately():
    route = (ROOT / "apps/api/app/routes/inventory.py").read_text()
    frontend = (ROOT / "apps/web/app/inventory/page.tsx").read_text()
    api = (ROOT / "apps/web/lib/api.ts").read_text()
    assert '@router.get("/movement-health")' in route
    assert 'require_permission("inventory.read")' in route
    assert 'accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)' in route
    assert 'ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)' in route
    assert "OUT_OF_STOCK_WITH_RECENT_DEMAND" in route
    assert "NO_SALE_90D" in route and "NO_SALE_60D" in route and "NO_SALE_30D" in route
    assert "units_sold_30d" in route and "units_returned_30d" in route
    assert "COALESCE(sr.inventory_location_id,source_sale.location_id)" in route
    assert "getInventoryMovementHealth" in api
    assert '"Stock Health"' in frontend
    assert "No completed sale found" in frontend
    assert "idx_sales_inventory_movement_history" in (ROOT / "migrations/038_phase6_movement_health_indexes.sql").read_text()
