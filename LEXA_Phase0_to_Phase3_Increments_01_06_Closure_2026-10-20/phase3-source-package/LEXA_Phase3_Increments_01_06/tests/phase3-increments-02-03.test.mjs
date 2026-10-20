import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
const root = new URL('../', import.meta.url).pathname;
const read = p => readFileSync(join(root, p), 'utf8');

test('workspace and onboarding pages fail visibly when APIs cannot be verified', () => {
  const workspace = read('overrides/apps/web/app/workspace/page.tsx');
  const onboarding = read('overrides/apps/web/app/onboarding/page.tsx');
  assert.match(workspace, /Could not load your workspaces/);
  assert.doesNotMatch(workspace, /workspace ID/i);
  assert.match(workspace, /selectWorkspace\(item\.tenant_id\)/);
  assert.match(onboarding, /Setup progress could not be verified/);
  assert.match(onboarding, /getSetupProgress/);
  assert.match(onboarding, /resume_path/);
});

test('team UI uses owner-managed API helpers and shows one-time invitation link handling', () => {
  const page = read('overrides/apps/web/app/administration/members/page.tsx');
  assert.match(page, /createWorkspaceInvitation/);
  assert.match(page, /replaceWorkspaceMemberBranches/);
  assert.match(page, /revokeWorkspaceInvitation/);
  assert.match(page, /navigator\.clipboard\.writeText/);
  assert.match(page, /one-time invitation link/i);
  assert.match(page, /Branch assignments are enforced on the core inventory, sales, returns/i);
  assert.match(page, /\["PENDING", "EXPIRED"\]\.includes\(invitation\.status\)/);
});

test('invite page previews invitation before accepting and routes through the server contract', () => {
  const page = read('overrides/apps/web/app/invite/page.tsx');
  assert.match(page, /previewWorkspaceInvitation/);
  assert.match(page, /acceptWorkspaceInvitation/);
  assert.match(page, /window\.location\.hash/);
  assert.match(page, /replaceState/);
  const api = read('overrides/apps/web/lib/api.phase3-increments-02-03.append.ts.txt');
  assert.match(api, /method: "POST"[\s\S]*body: JSON\.stringify\(\{ token \}\)/);
  assert.doesNotMatch(api, /invitations\/preview\?token=/);
  assert.match(page, /expires_at/);
  assert.match(page, /Ask the workspace owner to issue a new link/);
});

test('source overlay documents non-production safety and does not auto-run migration', () => {
  const script = read('scripts/apply_phase3_increments_02_03.py');
  const migration = read('overrides/migrations/030_phase3_workspace_memberships.sql');
  assert.match(script, /BASE_SHA/);
  assert.match(script, /working tree is not clean/i);
  assert.match(script, /combined Phase 3 Increments 01–06/i);
  assert.match(script, /does not run SQL, deploy, or contact production/i);
  assert.match(script, /public invitation routes do not require an existing session/);
  assert.match(script, /invitations/);
  assert.match(migration, /complete Phase 0–2 migration chain/);
  assert.match(migration, /tenant_invitations/);
  assert.doesNotMatch(migration, /CREATE TABLE public\.workspace_invitations/);
});

test('member role assignment is surfaced in API and admin UI', () => {
  const api = readFileSync(new URL('../overrides/apps/web/lib/api.phase3-increments-02-03.append.ts.txt', import.meta.url), 'utf8');
  const page = readFileSync(new URL('../overrides/apps/web/app/administration/members/page.tsx', import.meta.url), 'utf8');
  assert.match(api, /replaceWorkspaceMemberRoles/);
  assert.match(api, /role_ids: roleIds/);
  assert.match(page, /Save role assignments/);
  assert.match(page, /Only an existing workspace owner can grant the Owner role/);
});

test('branch assignment enforcement fails closed for stock and tenant-wide operations', () => {
  const helper = readFileSync(new URL('../overrides/apps/api/app/branch_access.py', import.meta.url), 'utf8');
  const inventory = readFileSync(new URL('../overrides/apps/api/app/routes/inventory.py', import.meta.url), 'utf8');
  const commerce = readFileSync(new URL('../overrides/apps/api/app/routes/commerce.py', import.meta.url), 'utf8');
  assert.match(helper, /Access to this branch has not been assigned/);
  assert.match(inventory, /accessible_location_ids/);
  assert.match(commerce, /require_full_branch_scope/);
});

test('role permission editor uses live owner-only role catalog contracts', () => {
  const page = readFileSync(new URL('../overrides/apps/web/app/administration/members/page.tsx', import.meta.url), 'utf8');
  const api = readFileSync(new URL('../overrides/apps/web/lib/api.phase3-increments-02-03.append.ts.txt', import.meta.url), 'utf8');
  const backend = readFileSync(new URL('../overrides/apps/api/app/routes/membership_admin.py', import.meta.url), 'utf8');
  assert.match(page, /Roles and permissions/);
  assert.match(page, /Save role permissions/);
  assert.match(api, /replaceWorkspaceRolePermissions/);
  assert.match(backend, /The built-in Owner role permission set is protected/);
});

test('financial aggregates and analytics refresh require branch-wide access', () => {
  const finance = readFileSync(new URL('../overrides/apps/api/app/routes/finance.py', import.meta.url), 'utf8');
  const analytics = readFileSync(new URL('../overrides/apps/api/app/routes/analytics.py', import.meta.url), 'utf8');
  assert.match(finance, /require_full_branch_scope/);
  assert.match(analytics, /membership_branch_assignments mba/);
  assert.match(analytics, /require_full_branch_scope/);
});
