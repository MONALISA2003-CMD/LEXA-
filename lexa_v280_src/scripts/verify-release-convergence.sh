#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python -m compileall -q apps/api/app
pytest -q
python - <<'PY'
from pathlib import Path
checks = {
    'apps/web/app/invite/page.tsx': ['Suspense', 'useSearchParams'],
    'apps/web/lib/api.ts': ['acceptInvitation'],
    'apps/api/app/health.py': ['def check_redis', '027_release_convergence'],
    'apps/api/app/auth.py': ['def accept_invitation', 'except Exception:', 'return False'],
    'apps/api/app/main.py': ['unhandled_request_exception', 'check_redis'],
    'migrations/021_phase5_analytics_foundation.sql': ["reference_type='SALE'"],
    'migrations/022_phase6a_brain_foundation.sql': ["current_setting(''app.tenant_id'', true)"],
    'migrations/027_release_convergence.sql': ['CREATE TABLE IF NOT EXISTS purchase_orders', '027_release_convergence'],
}
for rel, needles in checks.items():
    text = (Path(rel)).read_text()
    for needle in needles:
        assert needle in text, f'{rel}: missing {needle}'
print('release convergence source checks: PASS')
PY
