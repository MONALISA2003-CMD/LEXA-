from uuid import UUID, uuid4
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .health import check_database, check_redis
from .routes import auth, organization, rbac, catalog, inventory, commerce, finance, analytics, workspace_context, membership_admin, purchasing, team_chat
from .kernel import router as kernel_router
from .workers.analytics_outbox import run_embedded_worker
from .performance import RequestTelemetry, current_request_telemetry, elapsed_ms, format_server_timing, is_slow_request

logger = logging.getLogger("lexa.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run durable analytics refreshes once migration 041 is available.

    The worker is intentionally local to LEXA; multiple API replicas coordinate
    through PostgreSQL SKIP LOCKED, and shutdown cancels the polling task cleanly.
    """
    default_enabled = "true" if settings.app_env.strip().lower() == "production" else "false"
    enabled = os.getenv("ANALYTICS_REFRESH_WORKER_ENABLED", default_enabled).strip().lower() in {"1", "true", "yes", "on"}
    worker_task = asyncio.create_task(run_embedded_worker()) if enabled else None
    if enabled:
        logger.info("analytics_refresh_worker_enabled")
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="LEXA API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    incoming = request.headers.get("X-Request-ID", "").strip()
    try:
        request_id = str(UUID(incoming)) if incoming else str(uuid4())
    except ValueError:
        request_id = str(uuid4())
    request.state.request_id = request_id
    telemetry = RequestTelemetry(request_id=request_id)
    telemetry_token = current_request_telemetry.set(telemetry)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_request_error", extra={"request_id": request_id, "path": request.url.path, "method": request.method})
        response = JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "LEXA could not complete the request.", "request_id": request_id}})
    finally:
        current_request_telemetry.reset(telemetry_token)

    duration_ms = elapsed_ms(started_at, time.perf_counter())
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = format_server_timing(
        duration_ms,
        db_duration_ms=telemetry.db_duration_ms,
        db_query_count=telemetry.db_query_count,
    )
    log_fields = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "db_duration_ms": telemetry.db_duration_ms,
        "db_query_count": telemetry.db_query_count,
        "slow_db_query_count": telemetry.slow_db_query_count,
    }
    if response.status_code >= 500:
        logger.error(
            "request_failed_5xx request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f db_duration_ms=%.2f db_query_count=%s slow_db_query_count=%s",
            request_id, request.method, request.url.path, response.status_code,
            duration_ms, telemetry.db_duration_ms, telemetry.db_query_count,
            telemetry.slow_db_query_count, extra=log_fields,
        )
    if is_slow_request(duration_ms):
        logger.warning(
            "slow_request request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f db_duration_ms=%.2f db_query_count=%s slow_db_query_count=%s",
            request_id, request.method, request.url.path, response.status_code,
            duration_ms, telemetry.db_duration_ms, telemetry.db_query_count,
            telemetry.slow_db_query_count, extra=log_fields,
        )
    return response

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.app_env.strip().lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(organization.router, prefix="/api/v1")
app.include_router(workspace_context.router, prefix="/api/v1")
app.include_router(membership_admin.members_router, prefix="/api/v1")
app.include_router(membership_admin.invitations_router, prefix="/api/v1")
app.include_router(rbac.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(kernel_router, prefix="/api/v1")
app.include_router(commerce.router, prefix="/api/v1")
app.include_router(finance.router, prefix="/api/v1")
app.include_router(finance.compliance, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(purchasing.router, prefix="/api/v1")
app.include_router(team_chat.router, prefix="/api/v1")


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "lexa-api", "status": "ok", "version": app.version, "environment": settings.app_env}


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"], include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lexa-api", "environment": settings.app_env}


@app.get("/ready", tags=["system"])
@app.get("/api/ready", tags=["system"], include_in_schema=False)
def readiness() -> dict[str, object]:
    database_ok, database_error = check_database()
    cache_ok, cache_error = check_redis()
    ready = database_ok and cache_ok
    payload: dict[str, object] = {
        "status": "ready" if ready else "not_ready",
        "service": "lexa-api",
        "environment": settings.app_env,
        "dependencies": {
            "database": "ok" if database_ok else "error",
            "cache": "ok" if cache_ok else "error",
        },
    }
    if not ready:
        if settings.app_env.strip().lower() == "production":
            # Keep externally visible diagnostics stable and non-sensitive while
            # distinguishing an unavailable dependency from a schema mismatch.
            payload["failure_code"] = (
                "FEATURES_NEED_UPDATE"
                if database_error == "LEXA_SCHEMA_NOT_READY"
                else "SIGN_IN_NEEDS_UPDATE"
                if database_error == "LEXA_AUTH_SCHEMA_NOT_READY"
                else "BUSINESS_RECORDS_NEED_REVIEW"
                if database_error == "LEXA_DATABASE_NOT_CANONICAL"
                else "LEXA_DEPENDENCY_NOT_READY"
            )
        else:
            if not database_ok:
                payload["database_error_type"] = database_error
            if not cache_ok:
                payload["cache_error_type"] = cache_error
        response = JSONResponse(status_code=503, content=payload, headers={"Retry-After": "5"})
        return response
    return payload
