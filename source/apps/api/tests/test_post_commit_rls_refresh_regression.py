"""Regression contract for avoiding fragile post-commit ORM refreshes under forced RLS."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / "apps" / "api" / "app" / "routes"


def test_transaction_sensitive_routes_do_not_refresh_after_commit():
    # Render logs recorded SQLAlchemy "Could not refresh instance" failures for
    # POST /organization/branches and POST /catalog/categories after successful
    # commits. All affected endpoints flush before commit; SessionLocal explicitly
    # uses expire_on_commit=False, so an extra SELECT is neither needed nor safe
    # as a response-building step under transaction-local tenant/branch RLS.
    for filename in ("catalog.py", "organization.py", "rbac.py"):
        source = (ROUTES / filename).read_text()
        assert "db.refresh(" not in source, f"{filename} must not do a post-commit refresh"


def test_sqlalchemy_session_keeps_committed_response_state_without_refresh():
    source = (ROOT / "apps" / "api" / "app" / "db.py").read_text()
    assert "expire_on_commit=False" in source
    # The transaction hook is still responsible for re-applying tenant/user GUCs
    # on every new transaction for all normal subsequent requests.
    assert '@event.listens_for(Session, \"after_begin\")' in source
    assert "set_config('app.tenant_id', :tenant_id, true)" in source
