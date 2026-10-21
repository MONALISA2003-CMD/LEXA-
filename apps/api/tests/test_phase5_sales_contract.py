from pathlib import Path

SOURCE = Path(__file__).parents[1] / "app" / "routes" / "commerce.py"


def test_sales_history_supports_server_side_filters():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales")', 1)[1].split('@router.get("/sales/{sale_id}")', 1)[0]
    assert 'search: str | None = Query(default=None, max_length=100)' in block
    assert 'status: str | None = Query(default=None, max_length=20)' in block
    assert 'start_date: date | None = None' in block
    assert 'end_date: date | None = None' in block
    assert 'branch_id: UUID | None = None' in block
    assert 'LIMIT :lim OFFSET :off' in block
    assert 'public.lexa_business_date(s.created_at, :t) >= :start_date' in block
    assert 'public.lexa_business_date(s.created_at, :t) <= :end_date' in block


def test_sales_history_enforces_assigned_branch_scope():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales")', 1)[1].split('@router.get("/sales/{sale_id}")', 1)[0]
    assert 'membership_branch_assignments' in block
    assert "tm.status='ACTIVE'" in block
    assert "mba.status='ACTIVE'" in block
    assert 'ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=branch_id)' in block


def test_sale_detail_is_branch_authorized():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales/{sale_id}")', 1)[1].split('@router.post("/sales"', 1)[0]
    assert 'ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=sale["branch_id"])' in block
    assert 'Sale is not linked to an accessible branch' in block



def test_checkout_enforces_server_side_price_and_discount_capabilities():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales", status_code=201)', 1)[1].split('@router.get("/receivables")', 1)[0]
    assert "catalog.pricing.manage" in block
    assert "catalog.manage" in block
    assert "sales.manage" in block
    assert "Price override permission required" in block
    assert "Discount permission required" in block
    assert "No catalogue price is configured" in block
