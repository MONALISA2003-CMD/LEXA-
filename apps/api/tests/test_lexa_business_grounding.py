"""Pure contract tests for LEXA's local, source-grounded answer path."""
from datetime import date
from decimal import Decimal

from app.routes.ai_assistant import _business_fact_intent, _business_period_intent, _format_amount, _period_dates


def test_exact_sales_question_is_routed_to_local_records():
    assert _business_fact_intent("What were my sales yesterday?") == ("net_sales", "yesterday")
    assert _business_fact_intent("Show me net sales this week") == ("net_sales", "this week")
    assert _business_fact_intent("How much revenue did I record last 7 days?") == ("net_sales", "last 7 days")


def test_saved_payment_expense_and_margin_questions_are_local():
    assert _business_fact_intent("What payments were collected this month?") == ("payments_collected", "this month")
    assert _business_fact_intent("Show me expenses last month") == ("expenses_total", "last month")
    assert _business_fact_intent("What was my gross margin this week?") == ("gross_margin", "this week")


def test_stock_health_fact_question_uses_latest_snapshot():
    assert _business_fact_intent("What stock needs attention?") == ("stock_risk", "latest_snapshot")
    assert _business_fact_intent("How do I reduce stockouts?") is None


def test_advice_requests_are_not_misclassified_as_saved_facts():
    assert _business_fact_intent("How can I improve our sales process?") is None
    assert _business_fact_intent("How should I review this month's sales?") is None
    assert _business_fact_intent("How should I negotiate with suppliers?") is None


def test_period_windows_follow_the_business_date():
    as_of = date(2026, 10, 24)  # Saturday
    assert _period_dates(as_of, "today") == (as_of, as_of, "today")
    assert _period_dates(as_of, "yesterday") == (date(2026, 10, 23), date(2026, 10, 23), "yesterday")
    assert _period_dates(as_of, "this week") == (date(2026, 10, 19), as_of, "this week")
    assert _period_dates(as_of, "last week") == (date(2026, 10, 12), date(2026, 10, 18), "last week")


def test_amounts_use_decimal_rounding_and_missing_amounts_do_not_become_zero():
    assert _format_amount(Decimal("1200000.125")) == "1,200,000.13"
    import pytest
    with pytest.raises(ValueError, match="missing saved amount"):
        _format_amount(None)


def test_saved_sales_answer_is_local_permission_checked_and_evidence_linked(monkeypatch):
    from datetime import datetime, timezone
    import time
    import app.routes.ai_assistant as ai_module

    tenant_id = "tenant-fixture"
    user_id = "user-fixture"
    seen_scope = {}

    class Result:
        def __init__(self, *, scalar=None, row=None):
            self.scalar = scalar
            self.row = row

        def scalar_one_or_none(self):
            return self.scalar

        def mappings(self):
            return self

        def one(self):
            return self.row

    class FakeDB:
        def __init__(self):
            self.queries = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.queries.append((sql, params or {}))
            if "lexa_business_date" in sql:
                return Result(scalar=date(2026, 10, 24))
            if "FROM public.business_profiles" in sql:
                return Result(scalar="UGX")
            if "FROM public.analytics_refresh_runs" in sql:
                return Result(scalar=datetime.now(timezone.utc))
            if "FROM public.analytics_daily_business_metrics" in sql:
                return Result(row={
                    "record_count": 1,
                    "metric_total": Decimal("125000"),
                    "activity_count": 5,
                    "latest_business_date": date(2026, 10, 24),
                    "refreshed_at": datetime.now(timezone.utc),
                })
            raise AssertionError(f"Unexpected query: {sql[:160]}")

        def rollback(self):
            return None

    def require_scope(db, *, tenant_id, user_id):
        seen_scope.update(tenant_id=tenant_id, user_id=user_id)

    monkeypatch.setattr(ai_module, "require_full_branch_scope", require_scope)
    db = FakeDB()
    reply = ai_module._business_fact_answer(
        db, user_id=user_id, tenant_id=tenant_id,
        question="What were my sales yesterday?", request_started=time.monotonic(),
    )

    assert reply is not None
    assert reply.source_mode == "local_business_data"
    assert reply.evidence and reply.evidence["status"] == "available"
    assert reply.evidence["href"] == "/reports"
    assert "UGX 125,000.00" in reply.answer
    assert "2026-10-23" in reply.answer
    assert seen_scope == {"tenant_id": tenant_id, "user_id": user_id}
    assert any("public.analytics_daily_business_metrics" in sql for sql, _ in db.queries)
    assert not any("public.sales" in sql or "public.payments" in sql for sql, _ in db.queries)


def test_missing_analytics_refresh_never_returns_a_numeric_zero(monkeypatch):
    from datetime import datetime, timezone
    import time
    import app.routes.ai_assistant as ai_module

    class Result:
        def __init__(self, *, scalar=None, row=None):
            self.scalar = scalar
            self.row = row

        def scalar_one_or_none(self):
            return self.scalar

        def mappings(self):
            return self

        def one(self):
            return self.row

    class FakeDB:
        def __init__(self):
            self.queries = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.queries.append(sql)
            if "lexa_business_date" in sql:
                return Result(scalar=date(2026, 10, 24))
            if "FROM public.business_profiles" in sql:
                return Result(scalar="UGX")
            if "FROM public.analytics_refresh_runs" in sql:
                return Result(scalar=None)
            raise AssertionError(f"Unexpected query after stale refresh: {sql[:160]}")

        def rollback(self):
            return None

    monkeypatch.setattr(ai_module, "require_full_branch_scope", lambda *args, **kwargs: None)
    db = FakeDB()
    reply = ai_module._business_fact_answer(
        db, user_id="user-fixture", tenant_id="tenant-fixture",
        question="What were my sales yesterday?", request_started=time.monotonic(),
    )

    assert reply is not None
    assert reply.source_mode == "local_business_data"
    assert reply.evidence and reply.evidence["status"] == "unavailable"
    assert "not treated missing data as zero" in reply.answer
    assert not any("public.analytics_daily_business_metrics" in sql for sql in db.queries)


def test_assistant_endpoint_returns_grounded_metric_without_calling_provider(monkeypatch):
    from datetime import datetime, timezone
    import asyncio
    import app.routes.ai_assistant as ai_module
    from app.routes.ai_assistant import AssistRequest

    class Result:
        def __init__(self, *, scalar=None, row=None):
            self.scalar = scalar
            self.row = row

        def scalar_one_or_none(self):
            return self.scalar

        def mappings(self):
            return self

        def one(self):
            return self.row

    class FakeDB:
        def execute(self, statement, params=None):
            sql = str(statement)
            if "lexa_business_date" in sql:
                return Result(scalar=date(2026, 10, 24))
            if "FROM public.business_profiles" in sql:
                return Result(scalar="UGX")
            if "FROM public.analytics_refresh_runs" in sql:
                return Result(scalar=datetime.now(timezone.utc))
            if "FROM public.analytics_daily_business_metrics" in sql:
                return Result(row={
                    "record_count": 1,
                    "metric_total": Decimal("83000"),
                    "activity_count": 3,
                    "latest_business_date": date(2026, 10, 24),
                    "refreshed_at": datetime.now(timezone.utc),
                })
            raise AssertionError(f"Unexpected query: {sql[:160]}")

        def rollback(self):
            return None

    monkeypatch.setattr(ai_module, "require_full_branch_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(ai_module, "_enforce_rate_limit", lambda *args, **kwargs: asyncio.sleep(0))

    async def provider_must_not_run(*args, **kwargs):
        raise AssertionError("factual workspace figures must never be sent to an external model")

    monkeypatch.setattr(ai_module, "_generate", provider_must_not_run)
    reply = asyncio.run(ai_module.assistant(
        AssistRequest(prompt="What were my sales yesterday?"),
        ctx=(FakeDB(), "user-fixture", "tenant-fixture", "session-fixture"),
    ))

    assert reply.source_mode == "local_business_data"
    assert reply.provider == "lexa-local"
    assert reply.response_time_ms is not None and reply.response_time_ms < 15_000
    assert reply.evidence and reply.evidence["status"] == "available"
    assert "UGX 83,000.00" in reply.answer
