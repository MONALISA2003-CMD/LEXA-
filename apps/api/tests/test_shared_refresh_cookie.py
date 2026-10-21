import ast
from pathlib import Path

ROOT = Path(__file__).parents[1] / "app"
AUTH_SOURCE = ROOT / "auth.py"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def test_shared_refresh_cookie_helper_is_defined_in_auth_module():
    tree = _parse(AUTH_SOURCE)
    helpers = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_set_refresh_cookie"]
    assert len(helpers) == 1
    source = ast.get_source_segment(AUTH_SOURCE.read_text(), helpers[0]) or ""
    for contract in (
        '"lexa_refresh_token"',
        "httponly=True",
        'samesite="lax"',
        'path="/"',
        "settings.refresh_token_days * 86400",
        'settings.app_env.strip().lower() == "production"',
    ):
        assert contract in source


def test_all_shared_refresh_cookie_imports_resolve_to_auth_module():
    workspace = (ROOT / "routes" / "workspace_context.py").read_text()
    membership = (ROOT / "routes" / "membership_admin.py").read_text()
    auth_routes = (ROOT / "routes" / "auth.py").read_text()
    assert "from ..auth import create_access_token, new_refresh_token, hash_refresh_token, _set_refresh_cookie" in workspace
    assert any("_set_refresh_cookie" in line and "from ..auth import" in line for line in membership.splitlines())
    assert any("_set_refresh_cookie" in line and "from ..auth import" in line for line in auth_routes.splitlines())
    assert "def _set_refresh_cookie(" not in auth_routes
