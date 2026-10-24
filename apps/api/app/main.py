from uuid import UUID, uuid4
import asyncio
import logging
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .performance import elapsed_ms, format_server_timing, is_slow_request
from .health import check_database, check_redis
from .routes import (
    auth, organization, rbac, catalog, inventory, commerce, finance, analytics,
    workspace_context, membership_admin, purchasing, team_chat, ai_assistant,
)
from .kernel import router as kernel_router
from .intelligence.routes import router as intelligence_router
from .intelligence.document_routes import router as intelligence_documents_router
from .routes.transaction_evidence import router as transaction_evidence_router
from .routes.tax_reference import router as tax_reference_router
from .workers.analytics_outbox import run_embedded_worker

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
    """Correlate requests and expose safe API timing for performance diagnosis."""
    incoming = request.headers.get("X-Request-ID", "").strip()
    try:
        request_id = str(UUID(incoming)) if incoming else str(uuid4())
    except ValueError:
        request_id = str(uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    unhandled_error = False
    try:
        response = await call_next(request)
    except Exception:
        unhandled_error = True
        logger.exception("unhandled_request_error", extra={"request_id": request_id, "path": request.url.path, "method": request.method})
        response = JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "LEXA could not complete the request.", "request_id": request_id}})
    duration_ms = elapsed_ms(started_at, time.perf_counter())
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = format_server_timing(duration_ms)
    request_log_context = {
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }
    if is_slow_request(duration_ms):
        logger.warning(
            "slow_request request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
            extra=request_log_context,
        )
    if response.status_code >= 500 and not unhandled_error:
        logger.error(
            "request_failed_5xx request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
            extra=request_log_context,
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


@app.middleware("http")
async def block_legacy_ai_assist_route(request: Request, call_next):
    """Keep the old assistant URL closed so it cannot bypass the policy router.

    The interactive workspace uses /api/v1/ai/assistant, whose provider calls are
    gated by LEXA's central intelligence policy. This legacy path never reads or
    forwards a question to a provider.
    """
    if request.method.upper() == "POST" and request.url.path.rstrip("/") == "/api/v1/ai/assist":
        return JSONResponse(
            status_code=503,
            content={"detail": {
                "code": "AI_POLICY_GATE_REQUIRED",
                "message": "This older assistant route is disabled. Use the LEXA business assistant, which applies the current privacy and provider safety checks.",
            }},
        )
    return await call_next(request)


@app.middleware("http")
async def block_live_efris_submission(request: Request, call_next):
    """Keep fiscalisation manual-only; this deployment has no URA connector."""
    path = request.url.path.rstrip("/")
    if request.method.upper() == "POST" and path.startswith("/api/v1/compliance/sales/") and path.endswith("/fiscalize"):
        return JSONResponse(status_code=409, content={"detail": {
            "code": "EFRIS_MANUAL_ONLY",
            "message": "LEXA records tax calculations and official URA references only. Obtain the fiscal document through the official URA portal and record it in LEXA; no EFRIS submission is performed.",
        }})
    # Keep manual taxpayer details editable, but reject attempts to enable a
    # provider mode through the legacy configuration endpoint.
    if request.method.upper() == "PUT" and path == "/api/v1/compliance/efris/config":
        try:
            raw_body = await request.body()
            config_body = json.loads(raw_body or b"{}")
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "EFRIS configuration must be valid JSON."})
        if not isinstance(config_body, dict):
            return JSONResponse(status_code=400, content={"detail": "EFRIS configuration must be a JSON object."})
        if str(config_body.get("integration_mode", "MANUAL")).strip().upper() != "MANUAL":
            return JSONResponse(status_code=409, content={"detail": {
                "code": "EFRIS_MANUAL_ONLY",
                "message": "Only manual URA recordkeeping is available. LEXA does not support or enable system-to-system EFRIS integration.",
            }})
        consumed = False
        async def replay_body():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": raw_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}
        request._receive = replay_body
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID",
        "X-Document-Filename", "X-Document-Type", "X-Branch-ID",
    ],
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
app.include_router(transaction_evidence_router, prefix="/api/v1")
app.include_router(finance.router, prefix="/api/v1")
app.include_router(finance.compliance, prefix="/api/v1")
app.include_router(tax_reference_router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(purchasing.router, prefix="/api/v1")
app.include_router(team_chat.router, prefix="/api/v1")
app.include_router(ai_assistant.router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(intelligence_documents_router, prefix="/api/v1")


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
        return JSONResponse(status_code=503, content=payload, headers={"Retry-After": "5"})
    return payload
