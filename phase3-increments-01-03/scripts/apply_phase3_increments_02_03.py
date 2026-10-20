#!/usr/bin/env python3
"""Apply the combined Phase 3 Increments 01–03 candidate to a pinned LEXA checkout.

Source-copy patcher only: does not run SQL, deploy, or contact production.
"""
from __future__ import annotations
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

BASE_SHA = "8124cca301062eac6ffe59f68d02fc689a3ffae1"
ROOT = Path.cwd()
PACKAGE = Path(__file__).resolve().parents[1]
STRICT_GUARDS = {
    "apps/api/app/routes/auth.py": "dfe0f8bd204bc6b16908d61e311e75e53b420a98",
    "apps/api/app/main.py": "c6155bf8001e6e9341bb80ac84f3ae797c5210ee",
    "apps/api/app/routes/organization.py": "5150e386c1aed49daf46ed0f63264ee36eea04d9",
    "apps/web/components/app-shell.tsx": "b9763898c105048946be096b7e4352f7e28d232b",
    "apps/web/app/invite/page.tsx": "b71e004b83224045086ff6b95244ebd1a455a8a2",
    "apps/web/app/administration/page.tsx": "8ef73f5db57131b9e2f5783583157dc43c3462cc",
    "apps/web/lib/api.ts": "d62b1f64fc78bc333c1017a6bcda2690b8f3cb23",
}


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def read_target(repo_rel: str) -> str:
    path = ROOT / repo_rel
    if not path.is_file():
        fail(f"required source file not found: {repo_rel}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(f"source file is not UTF-8 text: {repo_rel}")


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        fail(f"expected exactly one anchor for {label}, found {count}")
    return source.replace(old, new, 1)


def main() -> None:
    if not (ROOT / ".git").exists():
        fail("run from the root of a real LEXA Git checkout")
    actual_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if actual_head != BASE_SHA:
        fail(f"HEAD is {actual_head}; this overlay is pinned to {BASE_SHA}. Rebase/revalidate instead of guessing.")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    if dirty.strip():
        fail("working tree is not clean; commit or stash local changes before applying this source overlay")

    for repo_rel, expected in STRICT_GUARDS.items():
        path = ROOT / repo_rel
        if not path.is_file():
            fail(f"required guarded source is missing: {repo_rel}")
        actual = blob_sha(path)
        if actual != expected:
            fail(f"source guard failed for {repo_rel}: expected blob {expected}, found {actual}. Review/rebase the patch first.")

    auth = read_target("apps/api/app/routes/auth.py")
    main_py = read_target("apps/api/app/main.py")
    shell = read_target("apps/web/components/app-shell.tsx")
    api = read_target("apps/web/lib/api.ts")

    if "lexa_list_active_user_workspaces" in auth:
        fail("Increment 02 login patch already appears present; refusing duplicate application")
    if "workspace_context.router" in main_py or "membership_admin.members_router" in main_py:
        fail("new routers already appear registered; refusing duplicate application")
    if "getWorkspaceOptions" in api or "Phase 3 Increment 02: authoritative workspace context" in api:
        fail("workspace API additions already appear present; refusing duplicate application")
    if "createBusinessProfile" in api or '"/administration/members"' in shell:
        fail("Increment 01 or 02/03 changes already appear present; refusing duplicate combined application")

    # Increment 01: business-profile and branch API client helpers required by onboarding.
    branch_type = 'export type Branch = { id:string; tenant_id:string; name:string; code:string; status:string };'
    profile_type = 'export type BusinessProfile = { id:string; tenant_id:string; legal_name:string; display_name:string; country_code:string; currency_code:string };\n'
    api = replace_exact(api, branch_type, profile_type + branch_type, "business profile type")
    branch_getter = 'export function getBranches() { return getJson<Branch[]>("/api/v1/organization/branches"); }'
    profile_helpers = '''export function getBusinessProfile() { return getJson<BusinessProfile | null>("/api/v1/organization/profile"); }
export function createBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}) { return getJson<BusinessProfile>("/api/v1/organization/profile", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}) { return getJson<BusinessProfile>("/api/v1/organization/profile", { method:"PATCH", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
'''
    api = replace_exact(api, branch_getter, profile_helpers + branch_getter, "business profile API helpers")
    warehouse_getter = 'export function getWarehouses() { return getJson<Warehouse[]>("/api/v1/organization/warehouses"); }'
    branch_helpers = '''export function createBranch(body: {name:string; code:string}) { return getJson<Branch>("/api/v1/organization/branches", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateBranch(id:string, body: {name:string; code:string}) { return getJson<Branch>(`/api/v1/organization/branches/${encodeURIComponent(id)}`, { method:"PATCH", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
'''
    api = replace_exact(api, warehouse_getter, branch_helpers + warehouse_getter, "branch API helpers")

    # Increment 02: share only active workspaces with the login/switch flow.
    auth = replace_exact(
        auth,
        "SELECT tenant_id, tenant_name, membership_id FROM public.lexa_list_user_workspaces(:user_id)",
        "SELECT tenant_id, tenant_name, membership_id FROM public.lexa_list_active_user_workspaces(:user_id)",
        "active workspace enumeration in login",
    )
    auth = replace_exact(
        auth,
        '''    if not membership:
        raise HTTPException(401, "Invalid credentials")

    device = None
''',
        '''    active_tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE"))
    if not membership or not active_tenant:
        raise HTTPException(401, "Invalid credentials")

    device = None
''',
        "reject inactive target workspace during login",
    )

    main_py = replace_exact(
        main_py,
        "from .routes import auth, organization, rbac, catalog, inventory, commerce, finance, analytics",
        "from .routes import auth, organization, rbac, catalog, inventory, commerce, finance, analytics, workspace_context, membership_admin",
        "route imports",
    )
    main_py = replace_exact(
        main_py,
        'app.include_router(organization.router, prefix="/api/v1")\n',
        'app.include_router(organization.router, prefix="/api/v1")\n'
        'app.include_router(workspace_context.router, prefix="/api/v1")\n'
        'app.include_router(membership_admin.members_router, prefix="/api/v1")\n'
        'app.include_router(membership_admin.invitations_router, prefix="/api/v1")\n',
        "router registration",
    )

    # Public invitation preview/accept must never start the cookie-refresh dance.
    api = replace_exact(
        api,
        r'''function requiresSession(path: string): boolean {
  if (/^\/(health|ready)$/.test(path)) return false;
  if (/^\/api\/v1\/auth\/(login|register|refresh|logout)$/.test(path)) return false;
  return true;
}''',
        r'''function requiresSession(path: string): boolean {
  if (/^\/(health|ready)$/.test(path)) return false;
  if (/^\/api\/v1\/auth\/(login|register|refresh|logout)$/.test(path)) return false;
  // Invitation preview/accept are token-authorized public routes; they must not trigger cookie refresh.
  if (/^\/api\/v1\/invitations\/(preview|accept)(\?|$)/.test(path)) return false;
  return true;
}''',
        "public invitation routes do not require an existing session",
    )

    shell = replace_exact(
        shell,
        '  ["/administration", "Administration", "⚙"],\n  ["/settings", "Settings", "◌"],',
        '  ["/administration", "Administration", "⚙"],\n'
        '  ["/administration/members", "Team and access", "♙"],\n'
        '  ["/workspace", "Switch workspace", "↔"],\n'
        '  ["/onboarding", "Workspace setup", "✓"],\n'
        '  ["/settings", "Settings", "◌"],',
        "workspace, onboarding, and team navigation",
    )
    shell = replace_exact(
        shell,
        '<div className="workspace-switch"><small>WORKSPACE</small><strong>{session?.tenant_name || "Your business"}</strong><span aria-hidden="true">⌄</span></div>',
        '<Link className="workspace-switch" href="/workspace" aria-label="Switch workspace"><small>WORKSPACE</small><strong>{session?.tenant_name || "Your business"}</strong><span aria-hidden="true">⌄</span></Link>',
        "workspace switch affordance",
    )

    api_append = (PACKAGE / "overrides/apps/web/lib/api.phase3-increments-02-03.append.ts.txt").read_text(encoding="utf-8")
    api = api.rstrip() + "\n" + api_append.lstrip()
    new_invite = (PACKAGE / "overrides/apps/web/app/invite/page.tsx").read_text(encoding="utf-8")
    organization = (PACKAGE / "overrides/apps/api/app/routes/organization.py").read_text(encoding="utf-8")
    administration = (PACKAGE / "overrides/apps/web/app/administration.page.tsx").read_text(encoding="utf-8")

    replacements = {
        "apps/api/app/routes/organization.py": organization,
        "apps/web/app/administration/page.tsx": administration,
        "apps/api/app/routes/auth.py": auth,
        "apps/api/app/main.py": main_py,
        "apps/web/components/app-shell.tsx": shell,
        "apps/web/lib/api.ts": api,
        "apps/web/app/invite/page.tsx": new_invite,
    }
    new_files = {
        "apps/api/app/workspace_domain.py": PACKAGE / "overrides/apps/api/app/workspace_domain.py",
        "apps/api/app/workspace_models.py": PACKAGE / "overrides/apps/api/app/workspace_models.py",
        "apps/api/app/routes/workspace_context.py": PACKAGE / "overrides/apps/api/app/routes/workspace_context.py",
        "apps/api/app/routes/membership_admin.py": PACKAGE / "overrides/apps/api/app/routes/membership_admin.py",
        "apps/web/app/workspace/page.tsx": PACKAGE / "overrides/apps/web/app/workspace/page.tsx",
        "apps/web/app/onboarding/page.tsx": PACKAGE / "overrides/apps/web/app/onboarding/page.tsx",
        "apps/web/app/administration/members/page.tsx": PACKAGE / "overrides/apps/web/app/administration/members/page.tsx",
        "migrations/030_phase3_workspace_memberships.sql": PACKAGE / "overrides/migrations/030_phase3_workspace_memberships.sql",
        "migrations/reconstructed/005a_phase0_outbox_contract_reconciliation.replay-only.sql": PACKAGE / "overrides/migrations/reconstructed/005a_phase0_outbox_contract_reconciliation.replay-only.sql",
        "migrations/reconstructed/025a_phase2_membership_branch_contract_reconciliation.replay-only.sql": PACKAGE / "overrides/migrations/reconstructed/025a_phase2_membership_branch_contract_reconciliation.replay-only.sql",
        "migrations/reconstructed/clean_replay_order.json": PACKAGE / "overrides/migrations/reconstructed/clean_replay_order.json",
        "scripts/build_phase0_3_replay_candidates.py": PACKAGE / "scripts/build_phase0_3_replay_candidates.py",
    }
    generated_files = [
        "migrations/reconstructed/004_catalog_and_rbac_hardening.replay-equivalent.sql",
        "migrations/reconstructed/021_phase5_analytics_foundation.repair-candidate.sql",
    ]
    for target, source in new_files.items():
        if (ROOT / target).exists():
            fail(f"target already exists: {target}; refusing to overwrite a file")
        if not source.is_file():
            fail(f"packaged source is missing: {source}")
    for target in generated_files:
        if (ROOT / target).exists():
            fail(f"generated replay candidate already exists: {target}; inspect it manually")

    # Stage all content and validate it before replacing/copying any repo files.
    stage = ROOT / ".phase3-increments-02-03-stage"
    if stage.exists():
        fail(f"staging directory already exists: {stage}; inspect and remove it manually")
    stage.mkdir()
    try:
        for repo_rel, content in replacements.items():
            dest = stage / repo_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        for repo_rel, source in new_files.items():
            dest = stage / repo_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        build_cmd = [sys.executable, str(PACKAGE / "scripts/build_phase0_3_replay_candidates.py"),
                     "--source-root", str(ROOT), "--output-root", str(stage)]
        build = subprocess.run(build_cmd, cwd=ROOT, capture_output=True, text=True)
        if build.returncode != 0:
            fail("replay candidate staging failed: " + (build.stderr.strip() or build.stdout.strip()))
        for repo_rel in generated_files:
            if not (stage / repo_rel).is_file():
                fail(f"replay candidate generator did not create {repo_rel}")
        for repo_rel in replacements:
            dest = ROOT / repo_rel
            shutil.copyfile(stage / repo_rel, dest)
        for repo_rel in [*new_files, *generated_files]:
            dest = ROOT / repo_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage / repo_rel, dest)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print("Applied combined Phase 3 Increments 01–03 candidate overlay and generated explicitly labelled clean-replay artifacts.")
    print("NOT run: migrations, database writes, tests, commits, CI, deployment, or hosted changes.")
    print("The 004 equivalent and 021 repair candidate preserve their original-source paths and are not historical originals.")
    print("Review the diff, strict source-recovery manifest, and closure matrix before any database/release action.")


if __name__ == "__main__":
    main()
