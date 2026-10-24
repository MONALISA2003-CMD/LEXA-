from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.intelligence.forecasting import (
    BACKTEST_DAYS,
    FORECAST_VERSION,
    HISTORY_DAYS,
    seasonal_weekday_forecast,
)

AS_OF = date(2026, 10, 24)
HISTORY_START = AS_OF - timedelta(days=HISTORY_DAYS - 1)


def weekday_history():
    # Exact weekly repeats make this deterministic seasonal baseline perfect.
    return [Decimal((HISTORY_START + timedelta(days=offset)).weekday() + 1) for offset in range(HISTORY_DAYS)]


def test_weekday_median_forecast_returns_future_daily_units_and_rolling_backtest():
    result = seasonal_weekday_forecast(
        weekday_history(), history_start=HISTORY_START, as_of_date=AS_OF, horizon_days=14
    )
    assert result["status"] == "available"
    assert result["forecast_version"] == FORECAST_VERSION
    assert result["history_days"] == HISTORY_DAYS
    assert result["active_demand_days"] == HISTORY_DAYS
    assert len(result["forecast"]) == 14
    assert result["forecast"][0]["date"] == (AS_OF + timedelta(days=1)).isoformat()
    assert result["forecast"][0]["forecast_units"] == str((AS_OF + timedelta(days=1)).weekday() + 1) + ".000"
    assert result["backtest"]["test_days_evaluated"] == BACKTEST_DAYS
    assert result["backtest"]["mae_units"] == "0.000"
    assert result["backtest"]["wape_percent"] == "0.00"
    assert result["backtest"]["last_week_baseline_wape_percent"] == "0.00"
    assert result["backtest"]["comparison_to_baseline"] == "TIED_WITH_LAST_WEEK_BASELINE"


def test_sparse_history_is_unavailable_not_a_fabricated_zero_forecast():
    result = seasonal_weekday_forecast(
        [Decimal(0)] * HISTORY_DAYS, history_start=HISTORY_START, as_of_date=AS_OF
    )
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "INSUFFICIENT_DEMAND_HISTORY"
    assert "forecast" not in result


def test_incomplete_window_is_unavailable():
    result = seasonal_weekday_forecast(
        weekday_history()[:-1], history_start=HISTORY_START, as_of_date=AS_OF
    )
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "INCOMPLETE_HISTORY_WINDOW"
    assert "forecast" not in result


def test_holdout_with_zero_actual_demand_does_not_divide_by_zero_or_report_wape():
    history = weekday_history()
    history[HISTORY_DAYS - BACKTEST_DAYS:] = [Decimal(0)] * BACKTEST_DAYS
    result = seasonal_weekday_forecast(
        history, history_start=HISTORY_START, as_of_date=AS_OF, horizon_days=7
    )
    assert result["status"] == "partial"
    assert result["reason_code"] == "BACKTEST_WAPE_UNAVAILABLE_NO_TEST_DEMAND"
    assert result["backtest"]["wape_percent"] is None
    assert result["backtest"]["wape_unavailable_when_test_actuals_are_zero"] is True
    assert all(Decimal(day["forecast_units"]) >= 0 for day in result["forecast"])


@pytest.mark.parametrize("bad", [-1, "NaN", "Infinity", "not-a-number"])
def test_invalid_or_negative_units_are_rejected(bad):
    history = weekday_history()
    history[0] = bad
    with pytest.raises(ValueError, match="finite non-negative"):
        seasonal_weekday_forecast(history, history_start=HISTORY_START, as_of_date=AS_OF)


def test_history_window_must_end_on_as_of_date():
    with pytest.raises(ValueError, match="consecutive 56-day window"):
        seasonal_weekday_forecast(weekday_history(), history_start=HISTORY_START, as_of_date=AS_OF - timedelta(days=1))


def test_horizon_is_bounded():
    with pytest.raises(ValueError, match="between 7 and 28"):
        seasonal_weekday_forecast(weekday_history(), history_start=HISTORY_START, as_of_date=AS_OF, horizon_days=90)


def test_api_demands_recent_full_refresh_and_stays_read_only():
    source = (Path(__file__).resolve().parents[1] / "app/intelligence/routes.py").read_text(encoding="utf-8")
    route = source.split('@router.get("/demand-forecast")', 1)[1]
    assert "require_full_branch_scope" in route
    assert "from_date <= :history_start" in route
    assert "to_date >= :business_date" in route
    assert "completed_at >= now() - INTERVAL '72 hours'" in route
    assert "status = 'SUCCEEDED'" in route
    assert "analytics_product_daily_metrics" in route
    assert '"business_writes_performed": False' in route
    assert '"stockout_censoring_corrected": False' in route
    assert "db.commit(" not in route
    assert "INSERT INTO" not in route.upper()
    assert "DELETE FROM" not in route.upper()


def test_capabilities_exposes_python_forecasting_without_external_ai_or_writes():
    source = (Path(__file__).resolve().parents[1] / "app/intelligence/routes.py").read_text(encoding="utf-8")
    capabilities = source.split('@router.get("/capabilities")', 1)[1].split('@router.get("/daily-brief")', 1)[0]
    assert '"python_forecasting": True' in capabilities
    assert '"seasonal_demand_forecast": True' in capabilities
    assert '"execution_available": False' in capabilities
    assert '"automatic_business_writes": False' in capabilities


class FakeResult:
    def __init__(self, *, scalar=None, one=None, rows=None):
        self.scalar = scalar
        self.one_value = one
        self.rows_value = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def mappings(self):
        return self

    def one(self):
        return self.one_value

    def all(self):
        return self.rows_value


class FakeForecastDB:
    def __init__(self, *, refresh_at, rows):
        self.refresh_at = refresh_at
        self.rows = rows
        self.calls = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params or {}))
        if "lexa_business_date" in sql:
            return FakeResult(scalar=AS_OF)
        if "analytics_refresh_runs" in sql:
            return FakeResult(one={"completed_at": self.refresh_at})
        if "WITH top_variants AS" in sql:
            return FakeResult(rows=self.rows)
        raise AssertionError(f"Unexpected SQL: {sql[:100]}")


def synthetic_db_rows(*, active_days=56):
    from datetime import datetime, timezone

    rows = []
    for offset in range(HISTORY_DAYS):
        if offset >= active_days:
            continue
        day = HISTORY_START + timedelta(days=offset)
        rows.append({
            "variant_id": "variant-1",
            "product_id": "product-1",
            "sku": "SKU-1",
            "product_name": "Synthetic product",
            "variant_name": "Each",
            "business_date": day,
            "units_sold": Decimal(day.weekday() + 1),
        })
    return rows


def import_forecast_routes_with_dependency_stubs(monkeypatch):
    """Use real app dependencies in CI; isolate temporary stubs in the overlay-only fixture."""
    import importlib
    import sys
    import types

    if "app.intelligence.routes" in sys.modules:
        return sys.modules["app.intelligence.routes"]
    api_root = Path(__file__).resolve().parents[1]
    if (api_root / "app/dependencies.py").exists() and (api_root / "app/branch_access.py").exists():
        return importlib.import_module("app.intelligence.routes")

    dependencies = types.ModuleType("app.dependencies")
    dependencies.require_permission = lambda _permission: (lambda: None)
    branch_access = types.ModuleType("app.branch_access")
    branch_access.require_full_branch_scope = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "app.dependencies", dependencies)
    monkeypatch.setitem(sys.modules, "app.branch_access", branch_access)
    intelligence_routes = importlib.import_module("app.intelligence.routes")
    # Do not leave a module with stubbed dependencies cached for later tests.
    sys.modules.pop("app.intelligence.routes", None)
    package = sys.modules.get("app.intelligence")
    if package is not None and getattr(package, "routes", None) is intelligence_routes:
        delattr(package, "routes")
    return intelligence_routes


def test_endpoint_fails_closed_when_full_window_refresh_is_not_recent(monkeypatch):
    from uuid import uuid4
    intelligence_routes = import_forecast_routes_with_dependency_stubs(monkeypatch)

    monkeypatch.setattr(intelligence_routes, "require_full_branch_scope", lambda *args, **kwargs: None)
    db = FakeForecastDB(refresh_at=None, rows=synthetic_db_rows())
    response = intelligence_routes.intelligence_demand_forecast(horizon_days=14, ctx=(db, uuid4(), uuid4(), uuid4()))
    assert response["status"] == "unavailable"
    assert response["reason_code"] == "FRESH_COMPLETE_HISTORY_REQUIRED"
    assert response["items"] == []
    assert response["history_coverage_verified"] is False
    assert not any("WITH top_variants AS" in sql for sql, _ in db.calls)


def test_endpoint_returns_backtested_read_only_forecast_after_fresh_covered_refresh(monkeypatch):
    from datetime import datetime, timezone
    from uuid import uuid4
    intelligence_routes = import_forecast_routes_with_dependency_stubs(monkeypatch)

    branch_scope_calls = []
    monkeypatch.setattr(
        intelligence_routes,
        "require_full_branch_scope",
        lambda *args, **kwargs: branch_scope_calls.append((args, kwargs)),
    )
    db = FakeForecastDB(refresh_at=datetime.now(timezone.utc), rows=synthetic_db_rows())
    response = intelligence_routes.intelligence_demand_forecast(horizon_days=14, ctx=(db, uuid4(), uuid4(), uuid4()))
    assert branch_scope_calls
    assert response["status"] == "available"
    assert response["history_coverage_verified"] is True
    assert response["external_ai_used"] is False
    assert response["business_writes_performed"] is False
    assert response["stockout_censoring_corrected"] is False
    assert len(response["items"]) == 1
    item = response["items"][0]
    assert item["product_name"] == "Synthetic product"
    assert len(item["forecast"]) == 14
    assert item["backtest"]["wape_percent"] == "0.00"
    assert all("INSERT INTO" not in sql.upper() and "DELETE FROM" not in sql.upper() for sql, _ in db.calls)


def test_endpoint_excludes_sparse_series_instead_of_fabricating_a_forecast(monkeypatch):
    from datetime import datetime, timezone
    from uuid import uuid4
    intelligence_routes = import_forecast_routes_with_dependency_stubs(monkeypatch)

    monkeypatch.setattr(intelligence_routes, "require_full_branch_scope", lambda *args, **kwargs: None)
    db = FakeForecastDB(refresh_at=datetime.now(timezone.utc), rows=synthetic_db_rows(active_days=5))
    response = intelligence_routes.intelligence_demand_forecast(horizon_days=14, ctx=(db, uuid4(), uuid4(), uuid4()))
    assert response["status"] == "unavailable"
    assert response["reason_code"] == "NO_ELIGIBLE_DEMAND_SERIES"
    assert response["items"] == []
    assert response["excluded_items"][0]["reason_code"] == "INSUFFICIENT_DEMAND_HISTORY"
