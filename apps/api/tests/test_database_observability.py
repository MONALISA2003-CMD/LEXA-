"""Tests for safe request-scoped SQL execution timing."""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import db_observability as db_metrics  # noqa: E402
from app.telemetry import (  # noqa: E402
    RequestTelemetry,
    bind_request_telemetry,
    current_request_telemetry,
    reset_request_telemetry,
)


def test_slow_sql_threshold_is_bounded_and_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("LEXA_SLOW_SQL_MS", "400")
    assert db_metrics.slow_sql_threshold_ms() == 400
    monkeypatch.setenv("LEXA_SLOW_SQL_MS", "1")
    assert db_metrics.slow_sql_threshold_ms() == 50
    monkeypatch.setenv("LEXA_SLOW_SQL_MS", "100000")
    assert db_metrics.slow_sql_threshold_ms() == 10_000
    monkeypatch.setenv("LEXA_SLOW_SQL_MS", "invalid")
    assert db_metrics.slow_sql_threshold_ms() == 250


def test_statement_classifier_never_returns_sql_or_parameter_values():
    sql = "SELECT * FROM payroll WHERE employee_email='private@example.com'"
    assert db_metrics.statement_operation(sql) == "SELECT"
    assert db_metrics.statement_operation("update sensitive_records set secret='x'") == "UPDATE"
    assert db_metrics.statement_operation("-- internal comment\nSELECT 1") == "OTHER"
    assert db_metrics.statement_operation(None) == "OTHER"


def test_request_telemetry_accumulates_only_finite_safe_measurements():
    telemetry = RequestTelemetry(request_id="request-123")
    token = bind_request_telemetry(telemetry)
    try:
        assert current_request_telemetry() is telemetry
        telemetry.record_database_query(2.345, slow=False)
        telemetry.record_database_query(7.5, slow=True)
        telemetry.record_database_query(float("nan"), slow=True)
        assert telemetry.db_query_count == 3
        assert telemetry.db_duration_ms == 9.85
        assert telemetry.slow_db_query_count == 1
    finally:
        reset_request_telemetry(token)
    assert current_request_telemetry() is None


def test_slow_query_log_contains_no_statement_or_parameter_values(monkeypatch, caplog):
    monkeypatch.setenv("LEXA_SLOW_SQL_MS", "50")
    monkeypatch.setattr(db_metrics.time, "perf_counter", lambda: 12.5)
    telemetry = RequestTelemetry(request_id="safe-correlation-id")
    token = bind_request_telemetry(telemetry)
    sql = "SELECT * FROM secret_table WHERE token='must-not-be-logged'"
    try:
        with caplog.at_level("WARNING", logger="lexa.database"):
            db_metrics._record_query(12.0, sql, False)
    finally:
        reset_request_telemetry(token)
    output = "\n".join(record.getMessage() for record in caplog.records)
    assert "slow_database_query" in output
    assert "safe-correlation-id" in output
    assert "operation=SELECT" in output
    assert "duration_ms=500.00" in output
    assert "secret_table" not in output
    assert "must-not-be-logged" not in output
    assert telemetry.db_query_count == 1
    assert telemetry.slow_db_query_count == 1


def test_database_observability_does_not_log_statement_or_parameters():
    source = (API_ROOT / "app" / "db_observability.py").read_text(encoding="utf-8")
    assert '"slow_database_query request_id=%s operation=%s duration_ms=%.2f executemany=%s"' in source
    assert "logger.warning" in source
    assert "parameters" in source  # event signature only; it is not interpolated or stored
    assert "statement" not in source.split('logger.warning(', 1)[1].split(')', 1)[0]


def test_database_listener_measures_real_sql_execution_without_a_network_database():
    from sqlalchemy import text
    from sqlalchemy.engine.create import create_engine as genuine_create_engine

    # A separate route-test module temporarily stubs sqlalchemy.create_engine at collection.
    engine = genuine_create_engine("sqlite://")
    db_metrics.install_database_observability(engine)
    db_metrics.install_database_observability(engine)  # listener installation is idempotent
    telemetry = RequestTelemetry(request_id="sqlite-test")
    token = bind_request_telemetry(telemetry)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
        assert telemetry.db_query_count == 1
        assert telemetry.db_duration_ms >= 0
        assert telemetry.slow_db_query_count == 0
    finally:
        reset_request_telemetry(token)
        engine.dispose()
