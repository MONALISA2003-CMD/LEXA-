"""Durably refresh tenant analytics and maintain a verified 56-day history window.

The worker stays embedded in the API. Migration 041 processes event-driven
single-day refreshes; migration 047 adds a separate, rate-limited history refresh
because demand forecasting intentionally refuses incomplete or stale histories.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..db import SessionLocal

logger = logging.getLogger("lexa.analytics_worker")
_history_migration_missing_reported = False


def configured_limits() -> tuple[int, int]:
    try:
        poll_seconds = int(os.getenv("ANALYTICS_WORKER_POLL_SECONDS", "10"))
    except ValueError:
        poll_seconds = 10
    try:
        batch_size = int(os.getenv("ANALYTICS_WORKER_BATCH_SIZE", "20"))
    except ValueError:
        batch_size = 20
    return max(2, min(poll_seconds, 60)), max(1, min(batch_size, 100))


def run_once(batch_size: int | None = None) -> dict[str, int] | None:
    """Process queued daily refreshes and, if installed, at most one 56-day backfill.

    The legacy three-key result is preserved for existing operational callers.
    Backfill counts are logged separately and never mixed with queue metrics.
    """
    global _history_migration_missing_reported
    _, default_batch = configured_limits()
    limit = default_batch if batch_size is None else max(1, min(int(batch_size), 100))
    with SessionLocal() as db:
        queue_function_exists = db.execute(
            text("SELECT to_regprocedure('public.process_analytics_refresh_queue(integer)') IS NOT NULL")
        ).scalar_one()
        if not queue_function_exists:
            db.rollback()
            return None
        result = db.execute(
            text("SELECT processed_count,failed_count,dead_letter_count FROM public.process_analytics_refresh_queue(:limit)"),
            {"limit": limit},
        ).mappings().one()

        history_function_exists = db.execute(
            text("SELECT to_regprocedure('public.refresh_analytics_forecast_baselines(integer)') IS NOT NULL")
        ).scalar_one()
        if history_function_exists:
            history = db.execute(
                text("SELECT processed_count,failed_count FROM public.refresh_analytics_forecast_baselines(:limit)"),
                {"limit": 1},
            ).mappings().one()
            history_processed = int(history["processed_count"] or 0)
            history_failed = int(history["failed_count"] or 0)
            if history_processed or history_failed:
                logger.info(
                    "analytics history backfill processed=%s failed=%s window_days=56",
                    history_processed, history_failed,
                )
            if history_failed:
                logger.error("analytics history backfill failed; the database recorded a retry cooldown")
            _history_migration_missing_reported = False
        elif not _history_migration_missing_reported:
            logger.warning("analytics history backfill idle: migration 047 is not installed")
            _history_migration_missing_reported = True
        db.commit()
    return {
        "processed": int(result["processed_count"] or 0),
        "failed": int(result["failed_count"] or 0),
        "dead_letter": int(result["dead_letter_count"] or 0),
    }


async def run_embedded_worker() -> None:
    """Lifecycle-safe loop called from the FastAPI lifespan handler."""
    poll_seconds, batch_size = configured_limits()
    logger.info("analytics refresh worker started poll_seconds=%s batch_size=%s", poll_seconds, batch_size)
    schema_missing_reported = False
    while True:
        try:
            stats = await asyncio.to_thread(run_once, batch_size)
            if stats is None:
                if not schema_missing_reported:
                    logger.warning("analytics refresh worker idle: migration 041 is not installed")
                    schema_missing_reported = True
                await asyncio.sleep(max(poll_seconds, 30))
                continue
            if schema_missing_reported:
                logger.info("analytics refresh worker activated after schema became available")
                schema_missing_reported = False
            if stats["processed"] or stats["failed"] or stats["dead_letter"]:
                logger.info(
                    "analytics refresh batch processed=%s failed=%s dead_letter=%s",
                    stats["processed"], stats["failed"], stats["dead_letter"],
                )
            if stats["dead_letter"]:
                logger.error("analytics refresh queue has dead-letter items; operator review is required")
            if not stats["processed"] and not stats["failed"] and not stats["dead_letter"]:
                await asyncio.sleep(poll_seconds)
        except asyncio.CancelledError:
            logger.info("analytics refresh worker shutdown requested")
            raise
        except (SQLAlchemyError, OSError, ValueError):
            logger.exception("analytics refresh worker iteration failed; next poll will retry")
            await asyncio.sleep(max(poll_seconds, 15))


def main() -> int:
    """Standalone entry point retained for staging diagnostics/manual operation."""
    import signal
    stopped = False

    def stop(_signum: int, _frame: Any) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poll_seconds, batch_size = configured_limits()
    logger.info("analytics refresh worker started poll_seconds=%s batch_size=%s", poll_seconds, batch_size)
    while not stopped:
        try:
            stats = run_once(batch_size)
            if stats is None:
                logger.warning("migration 041 is not installed; retrying later")
            elif stats["processed"] or stats["failed"] or stats["dead_letter"]:
                logger.info("analytics refresh batch %s", stats)
                if stats["dead_letter"]:
                    logger.error("analytics refresh queue has dead-letter items; operator review is required")
            if stats is None or not any(stats.values()):
                time.sleep(poll_seconds)
        except (SQLAlchemyError, OSError, ValueError):
            logger.exception("analytics refresh worker iteration failed; next poll will retry")
            time.sleep(poll_seconds)
    logger.info("analytics refresh worker stopped")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    raise SystemExit(main())
