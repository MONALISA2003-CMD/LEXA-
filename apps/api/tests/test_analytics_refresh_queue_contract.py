from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT.parent.parent / "migrations" / "041_commerce_integrity_scaling.sql"
MAIN = ROOT / "app" / "main.py"
WORKER = ROOT / "app" / "workers" / "analytics_outbox.py"


def test_committed_outbox_events_enqueue_coalesced_tenant_date_refresh():
    sql = MIGRATION.read_text()
    for event in (
        "SALE_COMPLETED",
        "RETURN_CREATED",
        "EXPENSE_POSTED",
        "EXPENSE_REVERSED",
        "inventory.adjustment.posted.v1",
        "inventory.stock_count.posted.v1",
        "inventory.transfer.completed.v1",
        "inventory.transfer.received.v1",
    ):
        assert event in sql
    assert "AFTER INSERT ON public.outbox_events" in sql
    assert "UNIQUE(tenant_id,business_date)" in sql
    assert "generation=public.analytics_refresh_queue.generation+1" in sql
    assert "interval '5 seconds'" in sql


def test_refresh_worker_is_bounded_retriable_and_multi_replica_safe():
    sql = MIGRATION.read_text()
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "'DEAD_LETTER'" in sql
    assert "process_analytics_refresh_queue(integer)" in sql
    assert "source_fiscal_document_id" in sql
    assert "GRANT EXECUTE ON FUNCTION public.process_analytics_refresh_queue(integer) TO lexa_app" in sql
    assert "REVOKE ALL ON public.analytics_refresh_queue FROM lexa_app" in sql


def test_api_lifecycle_starts_and_cancels_embedded_queue_worker():
    main = MAIN.read_text()
    worker = WORKER.read_text()
    assert "lifespan=lifespan" in main
    assert "asyncio.create_task(run_embedded_worker())" in main
    assert "worker_task.cancel()" in main
    assert "to_regprocedure('public.process_analytics_refresh_queue(integer)')" in worker
    assert "public.process_analytics_refresh_queue(:limit)" in worker
