from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_analytics_currency_is_explicit_at_api_boundary():
    source = (ROOT / "apps/api/app/routes/analytics.py").read_text(encoding="utf-8")
    assert source.count("currency_code: str = Query(..., min_length=3, max_length=3)") == 6
    assert 'currency_code: str = Query(default="UGX"' not in source


def test_frontend_analytics_helpers_require_an_explicit_currency():
    source = (ROOT / "apps/web/lib/api.ts").read_text(encoding="utf-8")
    for name in ("getAnalyticsOverview", "getAnalyticsDaily", "getAnalyticsProducts", "getAnalyticsProductSummary", "getAnalyticsBranches", "getAnalyticsPaymentsByChannel"):
        line = next(line for line in source.splitlines() if line.startswith(f"export function {name}("))
        assert "currency:string" in line
        assert "currency='UGX'" not in line
