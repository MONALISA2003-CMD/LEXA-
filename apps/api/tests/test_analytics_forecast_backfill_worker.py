"""Unit tests for the optional 56-day analytics-history worker path."""
import app.workers.analytics_outbox as worker


class FakeResult:
    def __init__(self, value=None, mapping=None):
        self.value = value
        self.mapping = mapping or {}

    def scalar_one(self):
        return self.value

    def mappings(self):
        return self

    def one(self):
        return self.mapping


class FakeSession:
    def __init__(self, *, process_exists=True, history_exists=True):
        self.process_exists = process_exists
        self.history_exists = history_exists
        self.committed = False
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, _params=None):
        query = str(statement)
        self.queries.append(query)
        if "to_regprocedure('public.process_analytics_refresh_queue(integer)')" in query:
            return FakeResult(self.process_exists)
        if "to_regprocedure('public.refresh_analytics_forecast_baselines(integer)')" in query:
            return FakeResult(self.history_exists)
        if "FROM public.process_analytics_refresh_queue" in query:
            return FakeResult(mapping={"processed_count": 2, "failed_count": 0, "dead_letter_count": 0})
        if "FROM public.refresh_analytics_forecast_baselines" in query:
            return FakeResult(mapping={"processed_count": 1, "failed_count": 0})
        raise AssertionError(f"Unexpected query: {query}")

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def test_run_once_calls_bounded_history_backfill_when_migration_exists(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    result = worker.run_once(batch_size=15)
    assert result == {"processed": 2, "failed": 0, "dead_letter": 0}
    assert session.committed is True
    assert any("refresh_analytics_forecast_baselines" in query for query in session.queries)


def test_run_once_keeps_queue_worker_alive_before_migration_047(monkeypatch):
    session = FakeSession(history_exists=False)
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    result = worker.run_once(batch_size=3)
    assert result == {"processed": 2, "failed": 0, "dead_letter": 0}
    assert session.committed is True
    assert not any("FROM public.refresh_analytics_forecast_baselines" in query for query in session.queries)


def test_run_once_returns_none_when_legacy_queue_schema_is_missing(monkeypatch):
    session = FakeSession(process_exists=False)
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    assert worker.run_once(batch_size=3) is None
    assert not session.committed
