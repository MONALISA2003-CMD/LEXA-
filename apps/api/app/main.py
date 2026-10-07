from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .health import check_database
from .routes import auth, organization, rbac, catalog, inventory, commerce, finance, analytics
from .kernel import router as kernel_router

app = FastAPI(title="LEXA API", version="1.0.0")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "").strip()
    try:
        request_id = str(UUID(incoming)) if incoming else str(uuid4())
    except ValueError:
        request_id = str(uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "LEXA could not complete the request.", "request_id": request_id}})
    response.headers["X-Request-ID"] = request_id
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
app.include_router(rbac.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(kernel_router, prefix="/api/v1")
app.include_router(commerce.router, prefix="/api/v1")
app.include_router(finance.router, prefix="/api/v1")
app.include_router(finance.compliance, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")


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
    payload: dict[str, object] = {
        "status": "ready" if database_ok else "not_ready",
        "service": "lexa-api",
        "environment": settings.app_env,
        "dependencies": {"database": "ok" if database_ok else "error"},
    }
    if not database_ok:
        payload["database_error_type"] = database_error if settings.app_env.strip().lower() != "production" else "LEXA_DATABASE_NOT_READY"
    return payload
