from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_tenant_context_is_reapplied_at_each_transaction_start():
    hook = _function_source(ROOT / "app" / "db.py", "_set_application_role_per_transaction")
    assert "apply_application_role(connection)" in hook
    assert 'session.info.get("lexa_tenant_id")' in hook
    assert 'session.info.get("lexa_user_id")' in hook
    assert "set_config('app.tenant_id', :tenant_id, true)" in hook
    assert "set_config('app.user_id', :user_id, true)" in hook


def test_tenant_dependency_persists_context_before_first_query():
    body = _function_source(ROOT / "app" / "dependencies.py", "tenant_db")
    assert 'db.info["lexa_tenant_id"] = str(tenant_id)' in body
    assert 'db.info["lexa_user_id"] = str(user_id)' in body
    assert body.index('db.info["lexa_tenant_id"]') < body.index("db.execute(")
