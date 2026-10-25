import { expect, test } from '@playwright/test';

type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'manager';
  branch_id: string;
  currency_code: string;
  max_approval_amount: string;
  within_limit_purchase_order_id: string;
  over_limit_purchase_order_id: string;
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE7_APPROVAL_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const stagingHosts = (process.env.LEXA_PHASE7_STAGING_HOSTS || '').split(',').map(item => item.trim().toLowerCase()).filter(Boolean);
const storageState = process.env.LEXA_PHASE7_APPROVAL_STORAGE_STATE || process.env.LEXA_PHASE7_STORAGE_STATE || '';
test.use({ storageState: storageState || { cookies: [], origins: [] } });
const productionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE7_APPROVAL_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && fixture?.actor_role === 'manager'
  && !productionHosts.has(baseHost)
  && stagingHosts.includes(baseHost)
  && Boolean(storageState)
  && Boolean(fixture?.branch_id && fixture?.currency_code && fixture?.max_approval_amount && fixture?.within_limit_purchase_order_id && fixture?.over_limit_purchase_order_id);
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let liveAuthHeader = '';
function authHeaders() { return liveAuthHeader ? { Authorization: liveAuthHeader } : {}; }

async function requestJson(page: import('@playwright/test').Page, method: 'GET' | 'POST', path: string, data?: unknown, idempotencyKey?: string) {
  const headers: Record<string, string> = { ...authHeaders() };
  if (method === 'POST') headers['Content-Type'] = 'application/json';
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  const response = method === 'GET'
    ? await page.request.get(`${apiRoot}${path}`, { headers })
    : await page.request.post(`${apiRoot}${path}`, { headers, data: data ?? {} });
  return { response, body: await response.json().catch(() => null) };
}

// Both orders and the role-specific policy are pre-seeded on an isolated tenant:
// one order is below the Manager cap and one is above it. No production data is touched.
test.describe('Phase 7 approval threshold acceptance (isolated staging only)', () => {
  test.skip(!explicitlySafe, 'Requires manager QA auth, explicit staging allow-list, a configured currency-specific cap and two submitted orders in a disposable tenant.');

  test('rejects over-limit purchase approval and allows only the within-limit order', async ({ page }) => {
    const data = fixture!;
    expect(new URL(baseUrl).protocol).toBe('https:');
    const cap = Number(data.max_approval_amount);
    expect(Number.isFinite(cap) && cap >= 0).toBe(true);

    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const summaryWait = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/purchasing/summary') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/purchasing');
    await summaryWait;
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated manager session supplied a bearer token').toBe(true);

    const under = await requestJson(page, 'GET', `/purchasing/purchase-orders/${encodeURIComponent(data.within_limit_purchase_order_id)}`);
    expect(under.response.status()).toBe(200);
    expect(under.body.currency_code).toBe(data.currency_code);
    expect(Number(under.body.total)).toBeLessThanOrEqual(cap);
    expect(under.body.status).toBe('SUBMITTED');

    const over = await requestJson(page, 'GET', `/purchasing/purchase-orders/${encodeURIComponent(data.over_limit_purchase_order_id)}`);
    expect(over.response.status()).toBe(200);
    expect(over.body.currency_code).toBe(data.currency_code);
    expect(Number(over.body.total)).toBeGreaterThan(cap);
    expect(over.body.status).toBe('SUBMITTED');

    const rejected = await requestJson(page, 'POST', `/purchasing/purchase-orders/${encodeURIComponent(data.over_limit_purchase_order_id)}/approve`, { reason: 'Phase 7 approval cap acceptance' }, 'phase7-over-limit-rejected');
    expect(rejected.response.status(), JSON.stringify(rejected.body)).toBe(409);
    expect(rejected.body.detail.code).toBe('PURCHASE_APPROVAL_LIMIT_EXCEEDED');
    const stillSubmitted = await requestJson(page, 'GET', `/purchasing/purchase-orders/${encodeURIComponent(data.over_limit_purchase_order_id)}`);
    expect(stillSubmitted.response.status()).toBe(200);
    expect(stillSubmitted.body.status).toBe('SUBMITTED');

    const key = 'phase7-within-limit-approved';
    const accepted = await requestJson(page, 'POST', `/purchasing/purchase-orders/${encodeURIComponent(data.within_limit_purchase_order_id)}/approve`, { reason: 'Phase 7 within-limit acceptance' }, key);
    expect(accepted.response.status(), JSON.stringify(accepted.body)).toBe(200);
    expect(accepted.body.status).toBe('OPEN');
    const replay = await requestJson(page, 'POST', `/purchasing/purchase-orders/${encodeURIComponent(data.within_limit_purchase_order_id)}/approve`, { reason: 'Phase 7 within-limit acceptance' }, key);
    expect(replay.response.status(), JSON.stringify(replay.body)).toBe(200);
    expect(replay.body.id).toBe(accepted.body.id);
    expect(replay.body.status).toBe('OPEN');
  });
});
