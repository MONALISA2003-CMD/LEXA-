from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_phase5_analytics_migration_contract():
    source=(ROOT/"migrations/021_phase5_analytics_foundation.sql").read_text()
    for table in ["analytics_refresh_runs","analytics_daily_business_metrics","analytics_branch_daily_metrics","analytics_product_daily_metrics","analytics_customer_purchase_patterns","analytics_inventory_health_metrics"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "CREATE OR REPLACE FUNCTION refresh_analytics" in source
    assert "INSERT INTO schema_migrations(version) VALUES('021_phase5_analytics_foundation')" in source

def test_phase5_analytics_api_and_reports_surface():
    api=(ROOT/"apps/api/app/routes/analytics.py").read_text()
    page=(ROOT/"apps/web/app/reports/page.tsx").read_text()
    assert '@router.get("/overview")' in api
    assert '@router.get("/products")' in api
    assert '@router.get("/inventory-health")' in api
    assert '@router.post("/refresh")' in api
    assert "getAnalyticsOverview" in page
    assert "Rebuild analytics" in page
