"""Small dependency-free helpers for API response timing and slow-request alerts."""
from __future__ import annotations

import math
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock

DEFAULT_SLOW_REQUEST_MS = 500
MIN_SLOW_REQUEST_MS = 100
MAX_SLOW_REQUEST_MS = 10_000


@dataclass(slots=True)
class RequestTelemetry:
    """Per-request database counters shared across synchronous DB worker threads."""

    request_id: str
    db_duration_ms: float = 0.0
    db_query_count: int = 0
    slow_db_query_count: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def record_db_query(self, duration_ms: float) -> None:
        try:
            duration = float(duration_ms)
        except (TypeError, ValueError):
            duration = 0.0
        if not math.isfinite(duration):
            duration = 0.0
        duration = max(0.0, duration)
        try:
            configured_slow_db_ms = int(os.getenv("LEXA_SLOW_DB_QUERY_MS", "100"))
        except (TypeError, ValueError):
            configured_slow_db_ms = 100
        slow_db_threshold = min(10_000, max(1, configured_slow_db_ms))
        with self._lock:
            self.db_duration_ms = round(self.db_duration_ms + duration, 2)
            self.db_query_count += 1
            if duration >= slow_db_threshold:
                self.slow_db_query_count += 1


current_request_telemetry: ContextVar[RequestTelemetry | None] = ContextVar(
    "lexa_request_telemetry", default=None
)


def slow_request_threshold_ms() -> int:
    """Return a bounded threshold so malformed env values cannot break startup."""
    try:
        configured = int(os.getenv("LEXA_SLOW_REQUEST_MS", str(DEFAULT_SLOW_REQUEST_MS)))
    except (TypeError, ValueError):
        configured = DEFAULT_SLOW_REQUEST_MS
    return min(MAX_SLOW_REQUEST_MS, max(MIN_SLOW_REQUEST_MS, configured))


def elapsed_ms(started_at: float, finished_at: float) -> float:
    """Convert monotonic-clock readings to a finite, non-negative millisecond value."""
    duration = (finished_at - started_at) * 1000.0
    if not math.isfinite(duration):
        return 0.0
    return round(max(0.0, duration), 2)


def format_server_timing(
    duration_ms: float, *, db_duration_ms: float | None = None, db_query_count: int = 0
) -> str:
    """Format application and aggregate database timings for Server-Timing."""
    try:
        duration = float(duration_ms)
    except (TypeError, ValueError):
        duration = 0.0
    if not math.isfinite(duration):
        duration = 0.0
    metrics = [f"api;dur={max(0.0, duration):.2f}"]
    if db_query_count > 0:
        try:
            db_duration = float(db_duration_ms or 0.0)
        except (TypeError, ValueError):
            db_duration = 0.0
        if not math.isfinite(db_duration):
            db_duration = 0.0
        metrics.append(
            f'db;dur={max(0.0, db_duration):.2f};desc="{max(0, int(db_query_count))} queries"'
        )
    return ", ".join(metrics)


def is_slow_request(duration_ms: float, threshold_ms: int | None = None) -> bool:
    """Return whether an API response warrants a warning log."""
    threshold = slow_request_threshold_ms() if threshold_ms is None else min(
        MAX_SLOW_REQUEST_MS, max(MIN_SLOW_REQUEST_MS, int(threshold_ms))
    )
    try:
        duration = float(duration_ms)
    except (TypeError, ValueError):
        return False
    return math.isfinite(duration) and duration >= threshold
