from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase0_smoke_script_checks_readiness_and_bodyless_auth_contracts():
    source = (ROOT / "scripts/smoke_phase0.py").read_text()
    for fragment in (
        '"/health"', '"/ready"', '"/api/v1/auth/refresh"',
        '"/api/v1/auth/logout"', '"/api/v1/auth/me"',
        '"/api/v1/catalog/products?limit=1"',
        'LEXA_SMOKE_EMAIL', 'LEXA_SMOKE_PASSWORD',
        'LEXA_SMOKE_TENANT_ID', 'before_refresh_cookie != after_refresh_cookie',
    ):
        assert fragment in source


def test_smoke_script_never_prints_password_or_refresh_cookie_values():
    source = (ROOT / "scripts/smoke_phase0.py").read_text()
    assert 'print(PASSWORD)' not in source
    assert 'print(before_refresh_cookie)' not in source
    assert 'print(after_refresh_cookie)' not in source
