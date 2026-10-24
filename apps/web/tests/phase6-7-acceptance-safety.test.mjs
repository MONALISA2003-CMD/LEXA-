import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const guard = read('../e2e/global-setup.ts');
const phase6 = read('../e2e/phase6-inventory-acceptance.spec.ts');
const phase7 = read('../e2e/phase7-authorization-acceptance.spec.ts');
const config = read('../playwright.config.ts');
const pkg = JSON.parse(read('../package.json'));

test('write-enabled staging guard requires explicit HTTPS host allow-list and denies production', () => {
  assert.match(guard, /LEXA_PHASE6_ALLOW_STAGING_WRITES/);
  assert.match(guard, /LEXA_PHASE7_ALLOW_STAGING_WRITES/);
  assert.match(guard, /restricted_purchase_order_id/);
  assert.match(guard, /target\.protocol !== 'https:'/);
  assert.match(guard, /productionHosts\.has\(host\)/);
  // The shared guard names this per-suite resolved allow-list `allowed`.
  assert.match(guard, /allowed(?:Hosts)?\.includes\(host\)/);
  assert.match(guard, /redirect: 'error'/);
});

test('write-enabled staging guard validates disposable fixture, auth state and runtime readiness', () => {
  assert.match(guard, /disposable_scope !== true/);
  assert.match(guard, /reset_strategy !== 'dispose_test_tenant'/);
  assert.match(guard, /existsSync\(storagePath\)/);
  assert.match(guard, /readiness\.environment/);
  assert.match(guard, /readiness\.dependencies\?\.database !== 'ok'/);
  assert.match(guard, /readiness\.dependencies\?\.cache !== 'ok'/);
});

test('Phase 6 acceptance recomputes reorder math and proves advisory reads do not move stock', () => {
  assert.match(phase6, /replenishment\/policies/);
  assert.match(phase6, /replenishment\/recommendations/);
  assert.match(phase6, /Math\.max\(target - \(onHand - reserved\) - inbound, 0\)/);
  assert.match(phase6, /advisory_only/);
  assert.match(phase6, /afterBalance\)\.toEqual\(beforeBalance\)/);
  assert.match(phase6, /afterLedger\)\.toEqual\(beforeLedger\)/);
  assert.match(phase6, /restricted_location_id/);
});

test('Phase 7 acceptance explicitly probes cross-branch list, detail and mutation denial', () => {
  assert.match(phase7, /restricted_purchase_order_id/);
  assert.match(phase7, /out-of-branch order detail must be denied/);
  assert.match(phase7, /out-of-branch order mutation must be denied/);
  assert.match(phase7, /purchase-orders\?limit=500/);
});

test('Playwright config includes Phase 2, Phase 6/7 and disables retries of write-enabled flows', () => {
  assert.match(config, /2-transaction/);
  assert.match(config, /6-inventory/);
  assert.match(config, /7-authorization/);
  assert.match(config, /globalSetup/);
  assert.match(config, /retries: stagingWritesEnabled \? 0/);
  assert.equal(pkg.engines.node, '24.x');
  assert.ok(pkg.scripts['test:e2e:phase2']);
  assert.ok(pkg.scripts['test:e2e:phase6']);
  assert.ok(pkg.scripts['test:e2e:phase7:security']);
});
