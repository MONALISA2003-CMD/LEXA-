"""Request-scoped performance telemetry shared with synchronous SQLAlchemy calls.

Only bounded numeric timing/count fields and a request ID are kept here. No SQL,
query parameters, request bodies, tenant data, or credentials are stored.
"""
from __future__ import annotations

import math
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(slots=True)
class RequestTelemetry:
    request_id: str
    db_query_count: int = 0
    db_duration_ms: float = 0.0
    slow_db_query_count: int = 0

    def record_database_query(self, duration_ms: float, *, slow: bool = False) -> None:
        """Accumulate safe query measurements for the active HTTP request."""
        self.db_query_count += 1
        try:
            duration = float(duration_ms)
        except (TypeError, ValueError):
            duration = 0.0
        valid_duration = math.isfinite(duration)
        if not valid_duration:
            duration = 0.0
        self.db_duration_ms = round(self.db_duration_ms + max(0.0, duration), 2)
        if slow and valid_duration:
            self.slow_db_query_count += 1


_current_request_telemetry: ContextVar[RequestTelemetry | None] = ContextVar(
    "lexa_request_telemetry", default=None
)


def bind_request_telemetry(telemetry: RequestTelemetry) -> Token[RequestTelemetry | None]:
    """Bind measurements to the current request context and return its reset token."""
    return _current_request_telemetry.set(telemetry)


def reset_request_telemetry(token: Token[RequestTelemetry | None]) -> None:
    """Restore the prior context to prevent telemetry leaking between requests."""
    _current_request_telemetry.reset(token)


def current_request_telemetry() -> RequestTelemetry | None:
    return _current_request_telemetry.get()
