import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..');
const page = readFileSync(path.join(web, 'app', 'purchasing', 'page.tsx'), 'utf8');
const api = readFileSync(path.join(web, 'lib', 'api.ts'), 'utf8');
const spec = readFileSync(path.join(web, 'e2e', 'phase7-purchasing-acceptance.spec.ts'), 'utf8');
const config = readFileSync(path.join(web, 'playwright.config.ts'), 'utf8');
const pkg = JSON.parse(readFileSync(path.join(web, 'package.json'), 'utf8'));
const workflow = readFileSync(path.resolve(web, '..', '..', '.github', 'workflows', 'lexa-ci.yml'), 'utf8');

 test('Phase 7 workspace exposes supplier, order, receiving, return, bill and balance modules', () => {
  for (const label of ['Suppliers', 'Purchase orders', 'Receiving', 'Supplier returns', 'Bills & payments', 'Balances']) {
    assert.ok(page.includes(label), `missing purchasing workspace tab ${label}`);
  }
  for (const contract of ['createSupplier', 'updatePurchasingSupplier', 'createPurchaseOrder', 'approvePurchaseOrder', 'createPurchaseReceipt', 'postPurchaseReceipt', 'createPurchaseReturn', 'postPurchaseReturn', 'createSupplierBill', 'postSupplierBill', 'createSupplierPayment', 'postSupplierPayment', 'getSupplierBalances', 'getSupplierLedger']) {
    assert.ok(api.includes(contract), `missing API contract ${contract}`);
  }
});

test('supplier terms, effective supplier costs, landed cost and explicit invoice exceptions are visible', () => {
  for (const phrase of ['Payment terms (days)', 'Use supplier price', 'landed_costs', 'WAITING_RECEIPT', 'Allow bill before delivery', 'Stock changes when you confirm a delivery.']) {
    assert.ok(page.includes(phrase), `missing workflow/guardrail wording ${phrase}`);
  }
  assert.match(api, /Idempotency-Key/);
});

test('Phase 7 E2E is enabled in Playwright but fails closed unless explicit staging safeguards are present', () => {
  assert.match(pkg.scripts['test:e2e:phase7'], /phase7-purchasing-acceptance\.spec\.ts/);
  assert.match(config, /phase\(5-sales\|7-purchasing\|8-reports\)-acceptance/);
  assert.match(config, /LEXA_PHASE7_STORAGE_STATE/);
  assert.match(spec, /LEXA_PHASE7_ALLOW_STAGING_WRITES/);
  assert.match(spec, /disposable_scope === true/);
  assert.match(spec, /reset_strategy === 'dispose_test_tenant'/);
  assert.match(spec, /knownProductionHosts\.has\(baseHost\)/);
  assert.match(spec, /fixture\?\.environment === 'staging'/);
  assert.match(spec, /stagingHosts\.includes\(baseHost\)/);
  assert.match(spec, /test\.skip\(!explicitlySafe/);
  assert.match(workflow, /run_phase7_staging_e2e/);
  assert.match(workflow, /reset_strategy !== 'dispose_test_tenant'/);
  assert.match(workflow, /Known production hostname is forbidden for write-enabled E2E/);
  assert.match(workflow, /Remove authenticated storage state/);
});
