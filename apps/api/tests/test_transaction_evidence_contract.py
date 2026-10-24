from pathlib import Path


def test_sale_evidence_route_is_registered_and_branch_scoped():
    api_root = Path(__file__).resolve().parents[1] / "app"
    route_source = (api_root / "routes" / "transaction_evidence.py").read_text(encoding="utf-8")
    main_source = (api_root / "main.py").read_text(encoding="utf-8")

    assert '@router.get("/sales/{sale_id}/evidence")' in route_source
    assert 'Depends(require_permission("sales.read"))' in route_source
    assert "ensure_branch_access(db" in route_source
    assert "tenant_id = CAST(:tenant_id AS uuid)" in route_source
    assert "FROM outbox_events" in route_source
    assert "FROM audit_logs" in route_source
    assert "successful_sale_idempotency_records" in route_source
    assert "e.payload->>'sale_id' = :sale_id" in route_source
    assert "transaction_evidence_router" in main_source
    assert 'app.include_router(transaction_evidence_router, prefix="/api/v1")' in main_source


def test_sale_evidence_response_does_not_return_private_payloads_or_idempotency_keys():
    route_source = (
        Path(__file__).resolve().parents[1] / "app" / "routes" / "transaction_evidence.py"
    ).read_text(encoding="utf-8")
    response_section = route_source.split("# Do not return payloads", 1)[1]
    assert '"events": [dict(row) for row in events]' in response_section
    assert '"audit": [dict(row) for row in audits]' in response_section
    assert "idempotency_key" not in response_section
    assert '"payload":' not in response_section
