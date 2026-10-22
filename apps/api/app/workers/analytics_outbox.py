"""Durably refresh tenant analytics from committed LEXA outbox events.

The worker is embedded in each API process, so deploying it does not require a
separate billable service. PostgreSQL row locks and SKIP LOCKED coordinate
multiple API replicas. If migration 041 is not installed yet, the worker backs
off and retries rather than failing health checks or spamming logs.
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
    """Run one bounded batch, returning None until migration 041 is present."""
    _, default_batch = configured_limits()
    limit = default_batch if batch_size is None else max(1, min(int(batch_size), 100))
    with SessionLocal() as db:
        function_exists = db.execute(
            text("SELECT to_regprocedure('public.process_analytics_refresh_queue(integer)') IS NOT NULL")
        ).scalar_one()
        if not function_exists:
            db.rollback()
            return None
        result = db.execute(
            text("SELECT processed_count,failed_count,dead_letter_count FROM public.process_analytics_refresh_queue(:limit)"),
            {"limit": limit},
        ).mappings().one()
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
