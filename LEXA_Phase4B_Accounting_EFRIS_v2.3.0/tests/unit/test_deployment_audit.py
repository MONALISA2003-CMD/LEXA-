from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
API = ROOT / "apps/api"
MODELS = API / "app/models.py"
CATALOG = API / "app/routes/catalog.py"
CONFIG = API / "app/config.py"
REQUIREMENTS = API / "requirements.txt"
PYPROJECT = API / "pyproject.toml"


def test_no_sqlalchemy_declarative_attribute_named_metadata():
    tree = ast.parse(MODELS.read_text())
    offenders = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for node in cls.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "metadata":
                offenders.append(cls.name)
    assert offenders == []


def test_metadata_database_column_is_preserved_for_product_and_variant():
    source = MODELS.read_text()
    assert 'product_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)' in source
    assert 'variant_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)' in source


def test_catalog_routes_use_orm_safe_metadata_attributes():
    source = CATALOG.read_text()
    assert "product_metadata=body.metadata" in source
    assert "variant_metadata=body.metadata" in source
    assert "row.product_metadata = body.metadata" in source
    assert "row.variant_metadata = body.metadata" in source
    assert "ProductOut" in source and 'validation_alias="product_metadata"' in source
    assert "VariantOut" in source and 'validation_alias="variant_metadata"' in source
    assert "Product(metadata=" not in source
    assert "ProductVariant(metadata=" not in source


def test_no_psycopg2_dependency_or_dialect_remains():
    assert "psycopg2" not in REQUIREMENTS.read_text().lower()
    assert "psycopg2" not in PYPROJECT.read_text().lower()
    assert "psycopg2" not in CONFIG.read_text().lower() or "postgresql+psycopg2://" in CONFIG.read_text().lower()


def test_render_runtime_contract_is_intact():
    render = (ROOT / "render.yaml").read_text()
    assert "rootDir: apps/api" in render
    assert "pip install -r requirements.txt" in render
    assert "uvicorn app.main:app --host 0.0.0.0 --port $PORT" in render
    assert "healthCheckPath: /health" in render
    assert "key: DATABASE_APP_ROLE" in render


def test_health_import_contract_has_no_missing_redis_symbol():
    main = (API / "app/main.py").read_text()
    health = (API / "app/health.py").read_text()
    assert "check_redis" not in main
    assert "def check_database" in health


def test_system_routes_are_declared():
    source = (API / "app/main.py").read_text()
    assert '@app.get("/", tags=["system"])' in source
    assert '@app.get("/health"' in source
    assert '@app.get("/api/health"' in source
    assert '@app.get("/ready"' in source
    assert '@app.get("/api/ready"' in source


def test_readiness_requires_lexa_schema_sentinel():
    health = (API / "app/health.py").read_text()
    assert "LEXA_SCHEMA_NOT_READY" in health
    assert '"registration_requests"' in health
    assert '"business_profiles"' in health


def test_database_readiness_locks_to_canonical_lexa_branch():
    health = (API / "app/health.py").read_text()
    config = CONFIG.read_text()
    render = (ROOT / "render.yaml").read_text()
    assert "neon.branch_id" in health
    assert "LEXA_DATABASE_NOT_CANONICAL" in health
    assert 'lexa_neon_branch_id: str = "br-soft-star-b1dj2m2w"' in config
    assert "LEXA_NEON_BRANCH_ID" in render
    assert "br-soft-star-b1dj2m2w" in render



def test_kernel_router_is_imported_from_canonical_module():
    source = (API / "app/main.py").read_text()
    assert "from .kernel import router as kernel_router" in source
    assert "from .routes import auth, organization, rbac, catalog, inventory, commerce, finance, analytics" in source
    assert 'app.include_router(kernel_router, prefix="/api/v1")' in source
    assert "from .routes import auth, organization, rbac, catalog, inventory, kernel, business_engine" not in source


def test_business_engine_user_surface_is_removed():
    assert not (ROOT / "apps/web/app/business-engine/page.tsx").exists()
    page = (ROOT / "apps/web/app/page.tsx").read_text()
    assert "/business-engine" not in page


def test_frontend_boot_verifies_authenticated_workspace_access():
    page = (ROOT / "apps/web/app/page.tsx").read_text()
    assert "getLocations" in page
    assert "verifyWorkspaceAccess" in page

