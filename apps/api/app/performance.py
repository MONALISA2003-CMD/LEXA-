"""Small dependency-free helpers for API response timing and slow-request alerts."""
from __future__ import annotations

import math
import os

DEFAULT_SLOW_REQUEST_MS = 500
MIN_SLOW_REQUEST_MS = 100
MAX_SLOW_REQUEST_MS = 10_000


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


def format_server_timing(duration_ms: float) -> str:
    """Format the app-only timing value for the standard Server-Timing header."""
    try:
        duration = float(duration_ms)
    except (TypeError, ValueError):
        duration = 0.0
    if not math.isfinite(duration):
        duration = 0.0
    return f"api;dur={max(0.0, duration):.2f}"


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
