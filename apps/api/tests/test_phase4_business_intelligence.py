from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase4_branch_summary_is_bounded_read_only_and_branch_guarded():
    source = (ROOT / "app" / "routes" / "analytics.py").read_text(encoding="utf-8")
    route = source.split('@router.get("/branches/summary")', 1)[1].split('@router.get("/insights")', 1)[0]
    assert 'Depends(require_permission("analytics.read"))' in route
    assert "membership_branch_assignments" in route
    assert "366 days or less" in route
    assert "public.analytics_branch_daily_metrics" in route
    assert "a.tenant_id=:tenant_id" in route
    assert "GROUP BY a.branch_id" in route
    assert "SUM(a.net_sales)" in route
    assert "INSERT INTO" not in route.upper() and "DELETE FROM" not in route.upper()
    assert "db.commit(" not in route


def test_overview_gross_profit_uses_saved_product_margin_and_preserves_missingness():
    source = (ROOT / "app" / "routes" / "analytics.py").read_text(encoding="utf-8")
    route = source.split('@router.get("/overview")', 1)[1].split('@router.get("/payments-by-channel")', 1)[0]
    assert "analytics_product_daily_metrics" in route
    assert "SUM(gross_margin) AS gross_profit" in route
    assert '"gross_profit_record_count"' in route
    assert "else None" in route
    assert "require_full_branch_scope" in route


def test_phase4_reporting_date_uses_the_tenant_timezone_function():
    source = (ROOT / "app" / "intelligence" / "routes.py").read_text(encoding="utf-8")
    route = source.split('@router.get("/business-date")', 1)[1].split('@router.get("/daily-brief")', 1)[0]
    assert 'Depends(require_permission("analytics.read"))' in route
    assert "public.lexa_business_date(now(), CAST(:tenant_id AS uuid))" in route
    assert "tenant_id" in route
    assert "db.commit(" not in route
