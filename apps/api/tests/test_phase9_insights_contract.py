from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase9_insights_api_is_read_only_bounded_and_branch_guarded():
    source = (ROOT / "app" / "routes" / "analytics.py").read_text()
    route = source.split('@router.get("/insights")', 1)[1].split('@router.post("/refresh")', 1)[0]
    assert 'Depends(require_permission("analytics.read"))' in route
    assert "require_full_branch_scope" in route
    assert "period_days > 93" in route
    assert 'Literal["all", "sales", "margin", "stock", "balances"]' in route
    assert "analytics_daily_business_metrics" in route
    assert "analytics_product_daily_metrics" in route
    assert "analytics_inventory_health_metrics" in route
    assert "receivables" in route
    assert "supplier_ledger_entries" in route
    assert "analytics_refresh_runs" in route
    assert '"advisory_only": True' in route
    assert '"external_ai_used": False' in route
    assert "model-provided SQL" in route
    assert "POST" not in route and "INSERT INTO" not in route and "DELETE FROM" not in route


def test_phase9_insight_rules_keep_unavailable_stale_and_metric_provenance_explicit():
    source = (ROOT / "app" / "business_insights.py").read_text()
    assert "No saved sales metrics were found" in source
    assert "has not assumed that sales were zero" in source
    assert "This is not net profit." in source
    assert "Gross margin = net sales − COGS" in source
    assert "percentage_points" in source
    assert "stale_after_days" in source
    assert "items_needing_review" in source
