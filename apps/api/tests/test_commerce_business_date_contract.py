from pathlib import Path


def test_commerce_dashboard_defaults_and_filters_by_tenant_business_date() -> None:
    source = (Path(__file__).parents[1] / "app" / "routes" / "commerce.py").read_text(encoding="utf-8")
    assert "SELECT public.lexa_business_date(now(), :tenant_id)" in source
    assert "s.business_date=:business_date" in source
    assert "s.created_at::date=:business_date" not in source
    assert "s.business_date >= :start_date" in source
    assert "s.business_date <= :end_date" in source
