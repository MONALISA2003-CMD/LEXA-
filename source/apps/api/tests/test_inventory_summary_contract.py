from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_inventory_summary_aggregates_every_authorized_location_server_side():
    source = (ROOT / "app" / "routes" / "inventory.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "inventory_summary")
    body = ast.get_source_segment(source, function) or ""

    assert '@router.get("/summary")' in source
    assert 'Depends(require_permission("inventory.read"))' in body
    assert "accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)" in body
    assert "func.sum(InventoryBalance.stock_value)" in body
    assert "InventoryBalance.location_id.in_(allowed_locations)" in body
    assert "out_of_stock_rows" in body and "low_stock_rows" in body
    assert "ProductVariant.tenant_id == InventoryBalance.tenant_id" in body
    assert "Product.tenant_id == ProductVariant.tenant_id" in body
    assert "Location.tenant_id == InventoryBalance.tenant_id" in body
    assert ".limit(10)" in body, "only the actionable attention list should be capped"
    assert '"stock_value": str(summary["stock_value"] or 0)' in body


def test_balance_detail_endpoint_remains_bounded_and_branch_scoped():
    source = (ROOT / "app" / "routes" / "inventory.py").read_text(encoding="utf-8")
    assert '@router.get("/balances", response_model=list[BalanceOut])' in source
    assert "allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)" in source
    assert ".limit(limit)" in source
