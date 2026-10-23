"""Low-overhead SQL execution timing without logging statements or values."""
from __future__ import annotations

import logging
import math
import os
import re
import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from .telemetry import current_request_telemetry

logger = logging.getLogger("lexa.database")
DEFAULT_SLOW_SQL_MS = 250
MIN_SLOW_SQL_MS = 50
MAX_SLOW_SQL_MS = 10_000
_OPERATION_PATTERN = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CALL|MERGE|CREATE|ALTER|DROP|SET)\b",
    re.IGNORECASE,
)


def slow_sql_threshold_ms() -> int:
    """Return a bounded query threshold; malformed configuration is harmless."""
    try:
        configured = int(os.getenv("LEXA_SLOW_SQL_MS", str(DEFAULT_SLOW_SQL_MS)))
    except (TypeError, ValueError):
        configured = DEFAULT_SLOW_SQL_MS
    return min(MAX_SLOW_SQL_MS, max(MIN_SLOW_SQL_MS, configured))


def statement_operation(statement: str | None) -> str:
    """Return only the leading SQL operation, never the statement or parameters."""
    match = _OPERATION_PATTERN.match(statement or "")
    if not match:
        return "OTHER"
    return match.group(1).upper()


def _record_query(started_at: float | None, statement: str | None, executemany: bool) -> None:
    if started_at is None:
        return
    duration = max(0.0, (time.perf_counter() - started_at) * 1000.0)
    if not math.isfinite(duration):
        return
    threshold = slow_sql_threshold_ms()
    is_slow = duration >= threshold
    telemetry = current_request_telemetry()
    if telemetry is not None:
        telemetry.record_database_query(duration, slow=is_slow)
    if is_slow:
        request_id = telemetry.request_id if telemetry is not None else "-"
        operation = statement_operation(statement)
        logger.warning(
            "slow_database_query request_id=%s operation=%s duration_ms=%.2f executemany=%s",
            request_id,
            operation,
            duration,
            bool(executemany),
            extra={
                "request_id": request_id,
                "operation": operation,
                "duration_ms": round(duration, 2),
                "executemany": bool(executemany),
            },
        )


def _before_cursor_execute(
    connection: Any,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    if context is not None:
        context._lexa_db_started_at = time.perf_counter()
        context._lexa_db_executemany = bool(executemany)
        # Store only the operation name rather than retaining SQL text in the context.
        context._lexa_db_operation = statement_operation(statement)


def _after_cursor_execute(
    connection: Any,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    if context is not None:
        started_at = getattr(context, "_lexa_db_started_at", None)
        operation = getattr(context, "_lexa_db_operation", "OTHER")
        _record_query(started_at, operation, bool(executemany))
        context._lexa_db_started_at = None


def _handle_error(exception_context: Any) -> None:
    context = getattr(exception_context, "execution_context", None)
    if context is None:
        return
    started_at = getattr(context, "_lexa_db_started_at", None)
    if started_at is None:
        return
    operation = getattr(context, "_lexa_db_operation", "OTHER")
    executemany = bool(getattr(context, "_lexa_db_executemany", False))
    _record_query(started_at, operation, executemany)
    context._lexa_db_started_at = None


def install_database_observability(engine: Engine | None) -> None:
    """Attach timing listeners once; ignore import-only test stubs without an engine."""
    if engine is None:
        return
    listeners = (
        ("before_cursor_execute", _before_cursor_execute),
        ("after_cursor_execute", _after_cursor_execute),
        ("handle_error", _handle_error),
    )
    for name, listener in listeners:
        if not event.contains(engine, name, listener):
            event.listen(engine, name, listener)
