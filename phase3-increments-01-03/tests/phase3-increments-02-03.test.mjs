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
  assert.match(page, /branch-specific business endpoints still require enforcement/i);
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
  assert.match(script, /combined Phase 3 Increments 01–03/i);
  assert.match(script, /does not run SQL, deploy, or contact production/i);
  assert.match(script, /public invitation routes do not require an existing session/);
  assert.match(script, /invitations/);
  assert.match(migration, /complete Phase 0–2 migration chain/);
  assert.match(migration, /tenant_invitations/);
  assert.doesNotMatch(migration, /CREATE TABLE public\.workspace_invitations/);
});
