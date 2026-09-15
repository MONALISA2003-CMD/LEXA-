from fastapi import FastAPI
from .routes import auth, organization, rbac, catalog

app = FastAPI(title="LEXA API", version="0.1.0")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(organization.router, prefix="/api/v1")
app.include_router(rbac.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
