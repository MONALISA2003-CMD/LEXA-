from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import auth, organization, rbac, catalog

app = FastAPI(title="LEXA API", version="0.1.0")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lexa-api", "environment": settings.app_env}
