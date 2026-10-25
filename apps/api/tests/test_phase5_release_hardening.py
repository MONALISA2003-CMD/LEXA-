"""Phase 5 regression contracts for safe, manual-only sales acceptance."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api" / "app"


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_efris_middleware_blocks_submit_without_reading_request_payloads():
    source = (API / "main.py").read_text(encoding="utf-8")
    middleware = section(source, "async def block_live_efris_submission", "app.add_middleware(")
    assert "request.body" not in source
    assert "json.loads" not in source
    assert 'path.endswith("/fiscalize")' in middleware
    assert "EFRIS_MANUAL_ONLY" in middleware
    assert "no EFRIS submission is performed" in middleware


def test_efris_configuration_rejects_provider_modes_before_database_write():
    source = (API / "routes" / "finance.py").read_text(encoding="utf-8")
    route = section(source, '@compliance.put("/efris/config")', '@compliance.get("/fiscal-documents")')
    guard = route.index('if body.integration_mode != "MANUAL":')
    write = route.index("INSERT INTO efris_configurations")
    assert guard < write
    assert "EFRIS_MANUAL_ONLY" in route
    assert "SYSTEM_TO_SYSTEM" not in route[guard:write]


def test_checkout_requires_replay_safe_key_and_keeps_atomic_rollback():
    source = (API / "routes" / "commerce.py").read_text(encoding="utf-8")
    route = section(source, '@router.post("/sales", status_code=201)', '@router.get("/receivables")')
    assert 'Depends(require_permission("sales.complete"))' in route
    assert "IDEMPOTENCY_KEY_REQUIRED" in route
    assert "not idempotency_key or not idempotency_key.strip()" in route
    assert '_idempotency(db,tenant_id,idempotency_key,"commerce.sale.create"' in route
    assert "Price override permission required" in route
    assert "Discount permission required" in route
    assert "calculate_line_tax(" in route
    assert "post_ledger(" in route
    assert "INSERT INTO receivables" in route
    assert "post_sale_journal(:id,:u)" in route
    assert "post_sale_cogs_journal(:id,:u)" in route
    assert "except HTTPException:" in route and "db.rollback()" in route
    assert "except IntegrityError" in route and "db.rollback()" in route


def test_sales_never_enqueue_or_create_external_fiscal_documents():
    source = (API / "routes" / "commerce.py").read_text(encoding="utf-8")
    route = section(source, '@router.post("/sales", status_code=201)', '@router.get("/receivables")')
    assert "create_fiscal_document_for_sale" not in route
    assert "FISCALIZATION_QUEUED" not in route
    assert 'result["fiscal_document_id"] = None' in route
    assert 'result["fiscalization_status"] = "MANUAL_REQUIRED"' in route


def test_sale_and_return_detail_remain_tenant_and_branch_scoped():
    source = (API / "routes" / "commerce.py").read_text(encoding="utf-8")
    detail = section(source, '@router.get("/sales/{sale_id}")', '@router.post("/sales", status_code=201)')
    returns = section(source, '@router.get("/returns")', '@router.post("/sales/{sale_id}/returns", status_code=201)')
    create_return = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert 'Depends(require_permission("sales.read"))' in detail
    assert "ensure_branch_access" in detail
    assert "membership_branch_assignments" in returns
    assert "status='ACTIVE'" in returns
    assert 'Depends(require_permission("sales.return"))' in create_return
    assert "FOR UPDATE" in create_return
    assert "remaining_refund_balance" in create_return
    assert "ensure_branch_access" in create_return
    assert "ensure_location_access" in create_return
    assert "db.rollback()" in create_return


def test_period_module_has_typescript_declaration_for_mjs_import():
    runtime = ROOT / "apps" / "web" / "lib" / "intelligence-period.mjs"
    declaration = ROOT / "apps" / "web" / "lib" / "intelligence-period.d.mts"
    assert runtime.is_file() and declaration.is_file()
    assert "getIntelligencePeriodRange" in declaration.read_text(encoding="utf-8")
