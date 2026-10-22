import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const page = fs.readFileSync(path.join(root, 'apps/web/app/inventory/page.tsx'), 'utf8');
const api = fs.readFileSync(path.join(root, 'apps/web/lib/api.ts'), 'utf8');
const route = fs.readFileSync(path.join(root, 'apps/api/app/routes/inventory.py'), 'utf8');
const migration = fs.readFileSync(path.join(root, 'migrations/036_phase6_inventory_intelligence.sql'), 'utf8');

test('Phase 6 inventory intelligence is connected end-to-end without auto-posting stock or purchasing actions', () => {
  assert.match(page, /"Replenishment"/);
  assert.match(page, /RESTOCK SETTINGS/);
  assert.match(page, /WHY THESE ITEMS NEED ATTENTION/);
  assert.match(page, /This only gives suggestions; it will not place an order/);
  assert.match(api, /\/api\/v1\/inventory\/replenishment\/policies/);
  assert.match(api, /\/api\/v1\/inventory\/replenishment\/recommendations/);
  assert.match(api, /advisory_only/);
  assert.match(route, /require_permission\("inventory\.manage"\)/);
  assert.match(route, /require_permission\("inventory\.read"\)/);
  assert.match(route, /COALESCE\(sr\.inventory_location_id, source_sale\.location_id\)=p\.location_id/);
  assert.match(migration, /FORCE ROW LEVEL SECURITY/);
  assert.match(migration, /inventory_replenishment_policies_tenant_isolation/);
  assert.doesNotMatch(page, /createPurchaseOrder\s*\(/);
});
