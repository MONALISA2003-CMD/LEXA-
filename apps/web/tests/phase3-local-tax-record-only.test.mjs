import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..');
const repoApps = path.resolve(web, '..');
const read = (p) => fs.readFileSync(path.resolve(web, p), 'utf8');
const compliancePage = read('app/compliance/page.tsx');
const apiMain = fs.readFileSync(path.join(repoApps, 'api/app/main.py'), 'utf8');
const taxRoute = fs.readFileSync(path.join(repoApps, 'api/app/routes/tax_reference.py'), 'utf8');
const taxCalculator = fs.readFileSync(path.join(repoApps, 'api/app/uganda_tax_2026.py'), 'utf8');

test('Phase 3 tax calculations are local, dated, and disclose the conflicting VAT threshold sources', () => {
  assert.match(compliancePage, /Automatic tax estimates/);
  assert.match(compliancePage, /tax-estimate/);
  assert.match(taxCalculator, /2026-10-23/);
  assert.match(taxCalculator, /VAT_THRESHOLD_LATEST_URA_FAQ/);
  assert.match(taxCalculator, /VAT_THRESHOLD_OTHER_OFFICIAL_PAGE/);
  assert.match(taxCalculator, /calculate_presumptive_tax/);
  assert.match(taxCalculator, /calculate_paye/);
  assert.match(taxRoute, /no_external_submission/);
  assert.doesNotMatch(taxRoute, /requests\.(get|post|put|request)|httpx\.(get|post|put|request)|aiohttp/);
});

test('LEXA keeps official fiscal documents manual-only and blocks system-to-system mode', () => {
  assert.match(compliancePage, /URA \/ EFRIS — MANUAL ONLY/);
  assert.match(compliancePage, /Save official URA reference/);
  assert.match(compliancePage, /LEXA does not call URA/);
  assert.doesNotMatch(compliancePage, /SYSTEM_TO_SYSTEM|PENDING_INTEGRATION/);
  assert.match(apiMain, /EFRIS_MANUAL_ONLY/);
  assert.match(apiMain, /path\.endswith\("\/fiscalize"\)/);
  assert.match(apiMain, /path == "\/api\/v1\/compliance\/efris\/config"/);
  assert.match(apiMain, /integration_mode.*MANUAL/s);
  assert.match(taxRoute, /MANUAL_URA_PORTAL/);
  assert.match(taxRoute, /NOT_VERIFIED_BY_LEXA/);
  assert.match(taxRoute, /external_submission.*False/);
  assert.match(taxRoute, /require_trimmed_fdn/);
  assert.match(taxRoute, /This FDN is already recorded in this workspace/);
});

test('the existing payment workflow describes recording methods rather than payment processing', () => {
  const commercePath = path.join(repoApps, 'web/app/commerce/page.tsx');
  const apiPath = path.join(repoApps, 'api/app/routes/commerce.py');
  if (fs.existsSync(commercePath)) {
    const commercePage = fs.readFileSync(commercePath, 'utf8');
    assert.match(commercePage, /Choose how money is recorded/);
    assert.match(commercePage, /No account numbers, PINs, OTPs, passwords, API keys or access tokens are stored here/);
    assert.match(commercePage, /createPaymentChannel/);
  }
  if (fs.existsSync(apiPath)) {
    const commerceApi = fs.readFileSync(apiPath, 'utf8');
    assert.match(commerceApi, /payment_channels/);
    assert.doesNotMatch(commerceApi, /RequestToPay|api\.mtn\.com|momoapi\.momo\.africa|stripe\.com\/v1\/payments|paypal\.com\/v\d+\/checkout/);
    assert.doesNotMatch(commerceApi, /import requests|import httpx|from requests|from httpx/);
  }
});
