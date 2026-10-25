import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..');
const root = path.resolve(web, '..', '..');
const page = readFileSync(path.join(web, 'app', 'purchasing', 'approval-limits', 'page.tsx'), 'utf8');
const nav = readFileSync(path.join(web, 'lib', 'navigation.mjs'), 'utf8');
const api = readFileSync(path.join(root, 'apps', 'api', 'app', 'routes', 'purchasing_approval.py'), 'utf8');
const migration = readFileSync(path.join(root, 'migrations', '048_phase7_approval_limits_reversals_accounting.sql'), 'utf8');
const spec = readFileSync(path.join(web, 'e2e', 'phase7-reversal-acceptance.spec.ts'), 'utf8');
const approvalSpec = readFileSync(path.join(web, 'e2e', 'phase7-approval-limits-acceptance.spec.ts'), 'utf8');
const allocationSpec = readFileSync(path.join(web, 'e2e', 'phase7-partial-allocations-acceptance.spec.ts'), 'utf8');
const config = readFileSync(path.join(web, 'playwright.config.ts'), 'utf8');
const packageJson = JSON.parse(readFileSync(path.join(web, 'package.json'), 'utf8'));
const globalSetup = readFileSync(path.join(web, 'e2e', 'global-setup.ts'), 'utf8');

test('approval limit page is navigable, currency-explicit and wired to the guarded API', () => {
  assert.match(nav, /\["\/purchasing\/approval-limits", "Approval limits", "settings"\]/);
  assert.match(nav, /\["Purchasing authorization limits", "\/purchasing\/approval-limits"\]/);
  assert.match(nav, /"\/purchasing\/approval-limits"/);
  assert.match(nav, /purchasing authorization|approval cap/i);
  assert.match(page, /\/purchasing\/approval-limits/);
  assert.match(page, /max_approval_amount/);
  assert.match(page, /No administrator approval limit|Owner and Administrator roles are the explicit override roles/);
  assert.match(page, /does not convert currencies automatically/i);
  assert.match(api, /@router\.get\("\/approval-limits"\)/);
  assert.match(api, /@router\.put\("\/approval-limits"\)/);
  assert.match(api, /Depends\(require_permission\("purchasing\.approval_limits\.manage"\)\)/);
});

test('supplier return reversal is append-only and cross-checks physical and accounting ledgers', () => {
  assert.match(api, /@router\.post\("\/returns\/\{return_id\}\/reverse"\)/);
  assert.match(api, /PURCHASE_RETURN_REVERSAL/);
  assert.match(api, /RETURN_REVERSAL/);
  assert.match(api, /@router\.get\("\/reconciliation"\)/);
  assert.match(migration, /trg_purchase_order_approval_limit/);
  assert.match(migration, /trg_purchasing_receipt_after_post/);
  assert.match(migration, /trg_purchasing_supplier_ledger_after_insert/);
  assert.match(migration, /REVOKE ALL PRIVILEGES/);
  assert.match(migration, /FORCE ROW LEVEL SECURITY/);
  assert.match(spec, /LEXA_PHASE7_REVERSAL_FIXTURE_JSON/);
  assert.match(spec, /LEXA_PHASE7_REVERSAL_ALLOW_STAGING_WRITES/);
  assert.match(spec, /supplier_ledger_entries_missing_journals/);
  assert.match(spec, /purchase_inventory_value_by_currency/);
  assert.match(spec, /unmapped_purchase_inventory_transactions/);
  assert.match(api, /purchase_inventory_value_by_currency/);
  assert.match(api, /no cross-currency netting/i);
  assert.match(approvalSpec, /PURCHASE_APPROVAL_LIMIT_EXCEEDED/);
  assert.match(approvalSpec, /LEXA_PHASE7_APPROVAL_ALLOW_STAGING_WRITES/);
  assert.match(approvalSpec, /within_limit_purchase_order_id/);
  assert.match(migration, /PURCHASE_APPROVAL_LIMIT_EXCEEDED_OR_NOT_CONFIGURED/);
  assert.match(migration, /purchase_approval_limits_tenant_isolation/);
  assert.match(globalSetup, /allowedRoles: \['owner', 'administrator'\]/);
  assert.match(globalSetup, /LEXA_PHASE7_APPROVAL_FIXTURE_JSON/);
  assert.match(config, /phase7ApprovalAcceptancePattern/);
  assert.match(config, /phase7-approval-limits-acceptance/);
  assert.match(packageJson.scripts['test:e2e:phase7'], /phase7-approval-limits-acceptance\.spec\.ts/);
});

test('partial supplier payments exercise two outstanding bills, replay safety and supplier-ledger reconciliation', () => {
  assert.match(allocationSpec, /LEXA_PHASE7_ALLOCATION_ALLOW_STAGING_WRITES/);
  assert.match(allocationSpec, /test\.skip\(!explicitlySafe/);
  assert.match(allocationSpec, /allocationA/);
  assert.match(allocationSpec, /allocationB/);
  assert.match(allocationSpec, /payment_amount/);
  assert.match(allocationSpec, /allocated_outstanding/);
  assert.match(allocationSpec, /supplier-ledger/);
  assert.match(allocationSpec, /supplier_ledger_entries_missing_journals/);
  assert.match(allocationSpec, /supplier_subledger_gl_mismatches/);
  assert.match(config, /phase7AllocationAcceptancePattern/);
  assert.match(globalSetup, /LEXA_PHASE7_ALLOCATION_FIXTURE_JSON/);
  assert.match(packageJson.scripts['test:e2e:phase7:allocation'], /phase7-partial-allocations-acceptance\.spec\.ts/);
});


test('purchasing reconciliation is a read-only user-facing control report', () => {
  const page = readFileSync(path.join(web, 'app', 'purchasing', 'reconciliation', 'page.tsx'), 'utf8');
  assert.match(nav, /\["\/purchasing\/reconciliation", "Purchasing reconciliation", "check"\]/);
  assert.match(page, /\/purchasing\/reconciliation/);
  assert.match(page, /read-only/i);
  assert.match(page, /stock_balance_ledger_mismatches/);
  assert.match(page, /supplier_subledger_gl_mismatches/);
  assert.match(page, /purchase_inventory_value_by_currency/);
});
