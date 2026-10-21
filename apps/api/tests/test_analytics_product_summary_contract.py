from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app" / "routes" / "analytics.py").read_text(encoding="utf-8")


def test_product_summary_aggregates_the_selected_range_before_ranking():
    source = _source()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "product_summary")
    body = ast.get_source_segment(source, function) or ""
    assert '@router.get("/products/summary")' in source
    assert 'Depends(require_permission("analytics.read"))' in body
    assert "require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)" in body
    assert "SUM(a.net_sales) AS net_sales" in body
    assert "SUM(a.gross_margin) AS gross_margin" in body
    assert "GROUP BY a.variant_id, a.product_id, pv.sku, p.name, pv.name, a.currency_code" in body
    assert "ORDER BY SUM(a.net_sales) DESC" in body
    assert "a.business_date BETWEEN :start_date AND :end_date" in body
    assert '"currency_code": currency_code.upper()' in body
    assert '"limit": limit' in body


def test_existing_daily_product_endpoint_is_preserved_for_detail_reports():
    source = _source()
    assert '@router.get("/products")' in source
    assert 'ORDER BY a.net_sales DESC LIMIT :limit' in source
