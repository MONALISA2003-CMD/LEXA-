from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from uuid import UUID, uuid4

from .config import settings
from .health import check_database
from .routes import auth, organization, rbac, catalog, inventory, kernel

app = FastAPI(title="LEXA API", version="0.1.4")

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "").strip()
    try:
        request_id = str(UUID(incoming)) if incoming else str(uuid4())
    except ValueError:
        request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
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
app.include_router(kernel.router, prefix="/api/v1")


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "service": "lexa-api",
        "status": "ok",
        "version": app.version,
        "environment": settings.app_env,
    }


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"], include_in_schema=False)
def health() -> dict[str, str]:
    """Liveness probe. Does not require dependencies to be reachable."""
    return {"status": "ok", "service": "lexa-api", "environment": settings.app_env}


@app.get("/ready", tags=["system"])
@app.get("/api/ready", tags=["system"], include_in_schema=False)
def readiness() -> dict[str, object]:
    """Readiness probe for the database dependency currently required by the API."""
    database_ok, database_error = check_database()
    payload: dict[str, object] = {
        "status": "ready" if database_ok else "not_ready",
        "service": "lexa-api",
        "environment": settings.app_env,
        "dependencies": {"database": "ok" if database_ok else "error"},
    }
    if not database_ok:
        payload["database_error_type"] = database_error
    return payload
