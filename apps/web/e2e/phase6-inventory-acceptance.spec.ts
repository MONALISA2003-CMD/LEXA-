import { expect, test } from '@playwright/test';

type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'owner' | 'administrator' | 'manager';
  location_id: string;
  restricted_location_id: string;
  variant_id: string;
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE6_ACCEPTANCE_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const allowedHosts = (process.env.LEXA_PHASE6_STAGING_HOSTS || '').split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
const storageState = process.env.LEXA_PHASE6_STORAGE_STATE || '';
const productionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE6_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && !productionHosts.has(baseHost)
  && allowedHosts.includes(baseHost)
  && Boolean(storageState)
  && Boolean(fixture?.location_id && fixture?.restricted_location_id && fixture?.variant_id);
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let liveAuthHeader = '';
function authHeaders() { return liveAuthHeader ? { Authorization: liveAuthHeader } : {}; }

type ApiReply = { response: import('@playwright/test').APIResponse; body: any };
async function requestJson(page: import('@playwright/test').Page, method: 'GET' | 'PUT', path: string, data?: unknown): Promise<ApiReply> {
  const options = { headers: { ...authHeaders(), ...(method === 'PUT' ? { 'Content-Type': 'application/json' } : {}) }, ...(method === 'PUT' ? { data: data ?? {} } : {}) };
  const response = method === 'GET'
    ? await page.request.get(`${apiRoot}${path}`, { headers: authHeaders() })
    : await page.request.put(`${apiRoot}${path}`, options);
  return { response, body: await response.json().catch(() => null) };
}
function numeric(value: unknown, label: string): number {
  const result = Number(value);
  expect(Number.isFinite(result), `${label} must be numeric`).toBe(true);
  return result;
}
function closeTo(actual: unknown, expected: number, label: string, tolerance = 0.00001) {
  expect(Math.abs(numeric(actual, label) - expected), `${label} must match the explainable formula`).toBeLessThanOrEqual(tolerance);
}
async function readBalance(page: import('@playwright/test').Page, locationId: string, variantId: string) {
  const query = new URLSearchParams({ location_id: locationId, variant_id: variantId, limit: '500' });
  const { response, body } = await requestJson(page, 'GET', `/inventory/balances?${query}`);
  expect(response.status(), 'inventory balance can be read for the fixture').toBe(200);
  expect(Array.isArray(body)).toBe(true);
  const row = (body as Array<Record<string, any>>).find((item) => item.location_id === locationId && item.variant_id === variantId);
  expect(row, 'the fixture has a materialized inventory balance').toBeTruthy();
  return {
    on_hand: String(row!.on_hand), reserved: String(row!.reserved ?? '0'), inbound: String(row!.inbound ?? '0'),
    stock_value: String(row!.stock_value ?? '0'),
  };
}
async function readLedgerIds(page: import('@playwright/test').Page, locationId: string, variantId: string) {
  const query = new URLSearchParams({ location_id: locationId, variant_id: variantId, limit: '500' });
  const { response, body } = await requestJson(page, 'GET', `/inventory/ledger?${query}`);
  expect(response.status(), 'inventory ledger can be read for the fixture').toBe(200);
  expect(Array.isArray(body)).toBe(true);
  return (body as Array<Record<string, any>>).map((row) => String(row.id)).sort();
}

// Writes are enabled only for a separate sanitized staging tenant. The global
// Playwright setup re-checks HTTPS, explicit host allow-list, auth state and the
// API's own environment/database/cache readiness before this spec can write.
test.describe('Phase 6 inventory intelligence acceptance (isolated staging only)', () => {
  test.skip(!explicitlySafe, 'Requires a dedicated staging host allow-list, disposable tenant fixture, QA auth state and LEXA_PHASE6_ALLOW_STAGING_WRITES=1.');

  test('policy upsert, explainable recommendation, movement/age views and stock-read non-mutation', async ({ page }) => {
    const data = fixture!;
    expect(['owner', 'administrator', 'manager']).toContain(data.actor_role);
    expect(new URL(baseUrl).protocol).toBe('https:');

    page.on('request', (request) => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const inventoryWait = page.waitForResponse((response) => response.url().includes('/api/lexa/api/v1/inventory/balances') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/inventory');
    await inventoryWait;
    await expect(page.getByText(/inventory/i).first()).toBeVisible();
    expect(liveAuthHeader.startsWith('Bearer '), 'browser session supplied an API bearer token').toBe(true);

    const beforeBalance = await readBalance(page, data.location_id, data.variant_id);
    const beforeLedger = await readLedgerIds(page, data.location_id, data.variant_id);
    const beforeIntegrity = await requestJson(page, 'GET', '/inventory/integrity');
    expect(beforeIntegrity.response.status()).toBe(200);
    expect(beforeIntegrity.body.status, 'fixture inventory starts reconciled').toBe('ok');

    const policyPayload = {
      location_id: data.location_id,
      variant_id: data.variant_id,
      lead_time_days: 7,
      review_period_days: 7,
      lookback_days: 30,
      minimum_available: '3',
      safety_stock: '2',
      enabled: true,
    };
    const firstPolicy = await requestJson(page, 'PUT', '/inventory/replenishment/policies', policyPayload);
    expect(firstPolicy.response.status(), 'manager can configure a location-scoped replenishment policy').toBe(200);
    expect(firstPolicy.body.enabled).toBe(true);
    const retryPolicy = await requestJson(page, 'PUT', '/inventory/replenishment/policies', policyPayload);
    expect(retryPolicy.response.status(), 'repeating the same scope updates the existing policy').toBe(200);
    expect(retryPolicy.body.id).toBe(firstPolicy.body.id);

    const policyQuery = new URLSearchParams({ location_id: data.location_id, variant_id: data.variant_id, limit: '500' });
    const savedPolicies = await requestJson(page, 'GET', `/inventory/replenishment/policies?${policyQuery}`);
    expect(savedPolicies.response.status()).toBe(200);
    expect(savedPolicies.body).toHaveLength(1);
    expect(savedPolicies.body[0].id).toBe(firstPolicy.body.id);

    const recQuery = new URLSearchParams({ location_id: data.location_id, include_covered: 'true', limit: '500' });
    const recommendations = await requestJson(page, 'GET', `/inventory/replenishment/recommendations?${recQuery}`);
    expect(recommendations.response.status(), 'replenishment recommendations are available').toBe(200);
    expect(recommendations.body.advisory_only, 'recommendations must not be automatic purchasing').toBe(true);
    const recommendation = (recommendations.body.items as Array<Record<string, any>>).find((item) => item.variant_id === data.variant_id && item.location_id === data.location_id);
    expect(recommendation, 'recommendation is scoped to the configured location and variant').toBeTruthy();

    const onHand = numeric(recommendation!.on_hand, 'on_hand');
    const reserved = numeric(recommendation!.reserved, 'reserved');
    const inbound = numeric(recommendation!.inbound, 'inbound');
    const sold = numeric(recommendation!.units_sold, 'units_sold');
    const returned = numeric(recommendation!.units_returned, 'units_returned');
    const netDemand = Math.max(sold - returned, 0);
    const dailyDemand = Number((netDemand / 30).toFixed(6));
    const target = Math.max(3, 2 + dailyDemand * (7 + 7));
    const expectedReorder = Number(Math.max(target - (onHand - reserved) - inbound, 0).toFixed(6));
    closeTo(recommendation!.net_units_demand, netDemand, 'net demand');
    closeTo(recommendation!.average_daily_demand, dailyDemand, 'daily demand');
    closeTo(recommendation!.target_stock, target, 'target stock');
    closeTo(recommendation!.reorder_quantity, expectedReorder, 'reorder quantity');
    expect(typeof recommendation!.methodology).toBe('string');
    expect(recommendation!.methodology).toContain('Completed SALE');

    const movement = await requestJson(page, 'GET', `/inventory/movement-health?${new URLSearchParams({ location_id: data.location_id, limit: '500' })}`);
    expect(movement.response.status(), 'movement-health view is available').toBe(200);
    expect(movement.body.source).toBe('completed_sales_returns_and_inventory_balances');
    const ageing = await requestJson(page, 'GET', `/inventory/ageing?${new URLSearchParams({ location_id: data.location_id, limit: '500' })}`);
    expect(ageing.response.status(), 'stock ageing view is available').toBe(200);

    const scopedDenied = await requestJson(page, 'PUT', '/inventory/replenishment/policies', { ...policyPayload, location_id: data.restricted_location_id });
    expect([403, 404], 'a location outside the actor scope must be denied').toContain(scopedDenied.response.status());
    const afterBalance = await readBalance(page, data.location_id, data.variant_id);
    const afterLedger = await readLedgerIds(page, data.location_id, data.variant_id);
    const afterIntegrity = await requestJson(page, 'GET', '/inventory/integrity');
    expect(afterIntegrity.response.status()).toBe(200);
    expect(afterIntegrity.body.status).toBe('ok');
    expect(afterBalance).toEqual(beforeBalance);
    expect(afterLedger).toEqual(beforeLedger);
  });
});
