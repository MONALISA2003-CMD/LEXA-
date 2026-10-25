import { expect, test } from '@playwright/test';

type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'owner' | 'administrator';
  posted_return_id: string;
  location_id: string;
  variant_id: string;
  supplier_party_id: string;
  currency_code: string;
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE7_REVERSAL_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const stagingHosts = (process.env.LEXA_PHASE7_STAGING_HOSTS || '').split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
const storageState = process.env.LEXA_PHASE7_REVERSAL_STORAGE_STATE || process.env.LEXA_PHASE7_STORAGE_STATE || '';
test.use({ storageState: storageState || { cookies: [], origins: [] } });
const knownProductionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE7_REVERSAL_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && !knownProductionHosts.has(baseHost)
  && stagingHosts.includes(baseHost)
  && Boolean(storageState)
  && Boolean(fixture?.posted_return_id && fixture?.location_id && fixture?.variant_id && fixture?.supplier_party_id && fixture?.currency_code);
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let liveAuthHeader = '';
function authHeaders() { return liveAuthHeader ? { Authorization: liveAuthHeader } : {}; }

type Reply = { response: import('@playwright/test').APIResponse; body: any };
async function requestJson(page: import('@playwright/test').Page, method: 'GET' | 'POST', path: string, data?: unknown, idempotencyKey?: string): Promise<Reply> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (method === 'POST') headers['Content-Type'] = 'application/json';
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  const response = method === 'GET'
    ? await page.request.get(`${apiRoot}${path}`, { headers })
    : await page.request.post(`${apiRoot}${path}`, { headers, data: data ?? {} });
  return { response, body: await response.json().catch(() => null) };
}
function numeric(value: unknown, name: string): number {
  const result = Number(value);
  expect(Number.isFinite(result), `${name} should be numeric`).toBe(true);
  return result;
}
async function readBalance(page: import('@playwright/test').Page, locationId: string, variantId: string) {
  const query = new URLSearchParams({ location_id: locationId, variant_id: variantId, limit: '500' });
  const { response, body } = await requestJson(page, 'GET', `/inventory/balances?${query}`);
  expect(response.status(), 'stock balance should be readable for the disposable fixture').toBe(200);
  expect(Array.isArray(body)).toBe(true);
  const row = body.find((item: Record<string, unknown>) => item.location_id === locationId && item.variant_id === variantId);
  expect(row, 'the posted supplier return should have a materialized balance').toBeTruthy();
  return { on_hand: String(row.on_hand), average_cost: String(row.average_cost), stock_value: String(row.stock_value) };
}

// A fresh, posted return is supplied by a disposable fixture. The test mutates
// only that tenant; it never targets production and has a single attempt.
test.describe('Phase 7 supplier-return reversal (isolated staging only)', () => {
  test.skip(!explicitlySafe, 'Requires explicit staging allow-list, owner/admin authentication and a posted return in a disposable tenant fixture.');

  test('reverses stock and supplier credit once, posts the journal reversal and reconciles', async ({ page }) => {
    const data = fixture!;
    expect(['owner', 'administrator']).toContain(data.actor_role);
    expect(new URL(baseUrl).protocol).toBe('https:');

    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const purchasingWait = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/purchasing/') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/purchasing');
    await purchasingWait;
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated workspace session should supply a bearer token').toBe(true);

    const before = await readBalance(page, data.location_id, data.variant_id);
    const ledgerQuery = new URLSearchParams({ location_id: data.location_id, variant_id: data.variant_id, limit: '500' });
    const { response: beforeLedgerResponse, body: beforeLedger } = await requestJson(page, 'GET', `/inventory/ledger?${ledgerQuery}`);
    expect(beforeLedgerResponse.status()).toBe(200);
    const returnOutflow = beforeLedger
      .filter((row: Record<string, any>) => row.transaction_type === 'PURCHASE_RETURN' && row.reference_id === data.posted_return_id)
      .reduce((sum: number, row: Record<string, any>) => sum + Math.abs(Number(row.quantity_delta)), 0);
    expect(returnOutflow, 'posted return has a corresponding original inventory movement').toBeGreaterThan(0);

    const key = `phase7-return-reversal-${data.posted_return_id}`;
    const payload = { reason: 'QA acceptance: reverse staged supplier return' };
    const first = await requestJson(page, 'POST', `/purchasing/returns/${encodeURIComponent(data.posted_return_id)}/reverse`, payload, key);
    expect(first.response.status(), JSON.stringify(first.body)).toBe(200);
    expect(first.body.status).toBe('REVERSED');
    expect(numeric(first.body.restored_quantity, 'restored quantity')).toBeCloseTo(returnOutflow, 6);

    const retry = await requestJson(page, 'POST', `/purchasing/returns/${encodeURIComponent(data.posted_return_id)}/reverse`, payload, key);
    expect(retry.response.status(), JSON.stringify(retry.body)).toBe(200);
    expect(retry.body.id).toBe(first.body.id);
    expect(retry.body.restored_quantity).toBe(first.body.restored_quantity);

    const after = await readBalance(page, data.location_id, data.variant_id);
    expect(numeric(after.on_hand, 'on-hand after reversal') - numeric(before.on_hand, 'on-hand before reversal'))
      .toBeCloseTo(numeric(first.body.restored_quantity, 'restored quantity'), 6);
    expect(Number(after.average_cost)).toBeGreaterThanOrEqual(0);
    expect(Number(after.stock_value)).toBeGreaterThanOrEqual(0);

    const { response: ledgerResponse, body: ledger } = await requestJson(page, 'GET', `/inventory/ledger?${ledgerQuery}`);
    expect(ledgerResponse.status()).toBe(200);
    const reversalRows = ledger.filter((row: Record<string, any>) => row.transaction_type === 'PURCHASE_RETURN_REVERSAL' && row.reference_id === data.posted_return_id);
    expect(reversalRows.length, 'a successful retry does not duplicate stock reversal rows').toBeGreaterThan(0);
    expect(reversalRows.reduce((sum: number, row: Record<string, any>) => sum + Number(row.quantity_delta), 0))
      .toBeCloseTo(numeric(first.body.restored_quantity, 'restored quantity'), 6);

    const reconciliation = await requestJson(page, 'GET', '/purchasing/reconciliation');
    expect(reconciliation.response.status(), JSON.stringify(reconciliation.body)).toBe(200);
    expect(reconciliation.body.checks.unbalanced_posted_journals).toBe(0);
    expect(reconciliation.body.checks.supplier_ledger_entries_missing_journals).toBe(0);
    expect(reconciliation.body.checks.supplier_subledger_gl_mismatches).toBe(0);
    expect(reconciliation.body.checks.unmapped_purchase_inventory_transactions).toBe(0);
    const valueByCurrency = reconciliation.body.purchase_inventory_value_by_currency as Array<Record<string, unknown>>;
    const valueForFixtureCurrency = valueByCurrency.find(row => row.currency_code === data.currency_code);
    expect(valueForFixtureCurrency, 'purchase stock and journal values are reconciled in the fixture currency').toBeTruthy();
    expect(Math.abs(Number(valueForFixtureCurrency!.difference))).toBeLessThanOrEqual(0.01);
  });
});
