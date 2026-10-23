import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

 type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'manager';
  restricted_purchase_order_id: string;
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE7_ACCEPTANCE_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const allowedHosts = (process.env.LEXA_PHASE7_STAGING_HOSTS || '').split(',').map((item) => item.trim().toLowerCase()).filter(Boolean);
const storageState = process.env.LEXA_PHASE7_STORAGE_STATE || process.env.LEXA_PHASE5_STORAGE_STATE || process.env.LEXA_PHASE4_STORAGE_STATE || '';
const productionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE7_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && fixture?.actor_role === 'manager'
  && !productionHosts.has(baseHost)
  && allowedHosts.includes(baseHost)
  && Boolean(storageState)
  && Boolean(fixture?.restricted_purchase_order_id);
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let liveAuthHeader = '';
function authHeaders() { return liveAuthHeader ? { Authorization: liveAuthHeader } : {}; }

async function requestJson(page: import('@playwright/test').Page, method: 'GET' | 'POST', path: string, data?: unknown, idempotencyKey?: string) {
  const response = method === 'GET'
    ? await page.request.get(`${apiRoot}${path}`, { headers: authHeaders() })
    : await page.request.post(`${apiRoot}${path}`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey || randomUUID() },
      data: data ?? {},
    });
  return { response, body: await response.json().catch(() => null) };
}

// The fixture's purchase order must belong to the same disposable tenant but a
// different branch for which the manager has no membership. Never run on prod.
test.describe('Phase 7 purchasing branch-boundary acceptance (isolated staging only)', () => {
  test.skip(!explicitlySafe, 'Requires staging host allow-list, restricted-branch fixture, QA auth state and LEXA_PHASE7_ALLOW_STAGING_WRITES=1.');

  test('list/detail/cancel cannot expose or mutate another branch purchase order', async ({ page }) => {
    const data = fixture!;
    expect(new URL(baseUrl).protocol).toBe('https:');
    page.on('request', (request) => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const summaryWait = page.waitForResponse((response) => response.url().includes('/api/lexa/api/v1/purchasing/summary') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/purchasing');
    await summaryWait;
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated staging session supplied a bearer token').toBe(true);

    const listed = await requestJson(page, 'GET', '/purchasing/purchase-orders?limit=500');
    expect(listed.response.status()).toBe(200);
    expect(Array.isArray(listed.body)).toBe(true);
    expect((listed.body as Array<Record<string, unknown>>).some((row) => row.id === data.restricted_purchase_order_id), 'the restricted order must not appear in branch-scoped listings').toBe(false);

    const detail = await requestJson(page, 'GET', `/purchasing/purchase-orders/${encodeURIComponent(data.restricted_purchase_order_id)}`);
    expect([403, 404], 'out-of-branch order detail must be denied without disclosing the record').toContain(detail.response.status());

    const cancelAttempt = await requestJson(page, 'POST', `/purchasing/purchase-orders/${encodeURIComponent(data.restricted_purchase_order_id)}/cancel`, { reason: 'Negative branch-scope acceptance probe; disposable test fixture only.' });
    expect([403, 404], 'out-of-branch order mutation must be denied').toContain(cancelAttempt.response.status());

    const listedAgain = await requestJson(page, 'GET', '/purchasing/purchase-orders?limit=500');
    expect(listedAgain.response.status()).toBe(200);
    expect((listedAgain.body as Array<Record<string, unknown>>).some((row) => row.id === data.restricted_purchase_order_id)).toBe(false);
  });
});
