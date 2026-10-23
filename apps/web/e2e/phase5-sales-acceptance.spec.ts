import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

type FixtureLine = { variant_id: string; quantity: string; unit_price: string };
type FixturePayment = { payment_channel_id: string; amount: string };
type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'cashier';
  location_id: string;
  branch_id?: string;
  customer_party_id: string;
  currency_code: string;
  business_date: string;
  cross_branch_sale_id?: string;
  cross_branch_sale_line_id?: string;
  cross_branch_return_id?: string;
  expected_total: string;
  expected_paid: string;
  lines: [FixtureLine, FixtureLine, FixtureLine];
  payments: [FixturePayment, FixturePayment];
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE5_ACCEPTANCE_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const stagingHosts = (process.env.LEXA_PHASE5_STAGING_HOSTS || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
const knownProductionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE5_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && !knownProductionHosts.has(baseHost)
  && stagingHosts.includes(baseHost)
  && Boolean(process.env.LEXA_PHASE5_STORAGE_STATE || process.env.LEXA_PHASE4_STORAGE_STATE);
const optedIn = Boolean(fixture) && explicitlySafe;
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let liveAuthHeader = '';
function authHeaders() { return liveAuthHeader ? { Authorization: liveAuthHeader } : {}; }

// Host allow-lists alone do not prove a preview is connected to a staging DB.
// Before any test can issue a write, require the proxied API to identify itself
// as staging/test and report healthy database + cache dependencies.
test.beforeAll(async () => {
  if (!optedIn) return;
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/lexa/ready`, { redirect: 'error' });
  expect(response.status, 'staging API readiness check succeeds').toBe(200);
  const readiness = await response.json() as { status?: string; environment?: string; dependencies?: { database?: string; cache?: string } };
  expect(['staging', 'test']).toContain(String(readiness.environment || '').toLowerCase());
  expect(readiness.status).toBe('ready');
  expect(readiness.dependencies?.database).toBe('ok');
  expect(readiness.dependencies?.cache).toBe('ok');
});

async function getJson(page: import('@playwright/test').Page, path: string) {
  const response = await page.request.get(`${apiRoot}${path}`, { headers: authHeaders() });
  const body = await response.json().catch(() => null);
  return { response, body };
}
async function readBalance(page: import('@playwright/test').Page, locationId: string, variantId: string) {
  const { response, body } = await getJson(page, `/inventory/balances?limit=500&location_id=${encodeURIComponent(locationId)}&variant_id=${encodeURIComponent(variantId)}`);
  expect(response.status(), 'read inventory balance').toBe(200);
  const row = (body as Array<{ location_id: string; variant_id: string; on_hand: string }>).find(x => x.location_id === locationId && x.variant_id === variantId);
  expect(row, `stock balance exists for variant ${variantId}`).toBeTruthy();
  return Number(row!.on_hand);
}

// This suite creates sales/returns and therefore runs only when the operator
// explicitly supplies a staging hostname allow-list, QA storage state and
// disposable seeded-fixture JSON. It cannot opt in on environment label alone.
test.describe('Phase 5 isolated staging sales acceptance', () => {
  test.skip(!optedIn, 'Requires explicit staging hostname allow-list, disposable fixture, QA auth state, and LEXA_PHASE5_ALLOW_STAGING_WRITES=1.');

  test('multi-line split tender, idempotent retry, payment/stock read-after-write, and cumulative refund cap', async ({ page }) => {
    const data = fixture!;
    expect(new URL(baseUrl).hostname.toLowerCase()).toBe(baseHost);
    expect(data.lines).toHaveLength(3);
    expect(data.payments).toHaveLength(2);
    expect(data.lines.map(line => Number(line.unit_price))).toEqual([8000, 3000, 4000]);
    expect(data.lines.every(line => Number(line.quantity) === 1)).toBe(true);
    expect(Number(data.expected_total)).toBe(15000);
    expect(Number(data.expected_paid)).toBe(10000);
    expect(data.lines.reduce((sum, line) => sum + Number(line.quantity) * Number(line.unit_price), 0)).toBe(Number(data.expected_total));
    expect(data.payments.reduce((sum, payment) => sum + Number(payment.amount), 0)).toBe(Number(data.expected_paid));

    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const dashboardRequest = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/commerce/dashboard') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/sales');
    await dashboardRequest;
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated browser session supplied its API bearer token').toBe(true);
    const balancesBefore = new Map<string, number>();
    for (const line of data.lines) balancesBefore.set(line.variant_id, await readBalance(page, data.location_id, line.variant_id));

    // Seed validation prevents accidentally asserting checkout against stale prices.
    const productsRead = await getJson(page, '/commerce/products');
    expect(productsRead.response.status()).toBe(200);
    const products = productsRead.body as Array<{ variant_id: string; selling_price: string; track_inventory: boolean }>;
    for (const line of data.lines) {
      const product = products.find(x => x.variant_id === line.variant_id);
      expect(product, `catalogue variant ${line.variant_id} exists`).toBeTruthy();
      expect(Number(product!.selling_price)).toBe(Number(line.unit_price));
      expect(product!.track_inventory).toBe(true);
    }

    const payload = {
      customer_party_id: data.customer_party_id,
      branch_id: data.branch_id,
      location_id: data.location_id,
      currency_code: data.currency_code,
      business_date: data.business_date,
      lines: data.lines.map(line => ({ ...line })),
      payments: data.payments.map(payment => ({ ...payment })),
    };
    const idempotencyKey = randomUUID();
    const firstResponse = await page.request.post(`${apiRoot}/commerce/sales`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey, 'X-Request-ID': randomUUID() },
      data: payload,
    });
    expect(firstResponse.status(), 'first checkout succeeds').toBe(201);
    const firstSale = await firstResponse.json() as { id: string; total: string; amount_paid: string; amount_due: string };
    expect(Number(firstSale.total)).toBe(Number(data.expected_total));
    expect(Number(firstSale.amount_paid)).toBe(Number(data.expected_paid));
    expect(Number(firstSale.amount_due)).toBe(Number(data.expected_total) - Number(data.expected_paid));

    const replayResponse = await page.request.post(`${apiRoot}/commerce/sales`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey, 'X-Request-ID': randomUUID() },
      data: payload,
    });
    expect(replayResponse.status(), 'idempotent retry replays successfully').toBe(201);
    const replay = await replayResponse.json() as { id: string };
    expect(replay.id).toBe(firstSale.id);

    const detailRead = await getJson(page, `/commerce/sales/${firstSale.id}`);
    expect(detailRead.response.status()).toBe(200);
    const detail = detailRead.body as {
      id: string; total: string; amount_paid: string; amount_due: string;
      lines: Array<{ sale_line_id: string; product_variant_id: string; line_total: string }>;
      payments: Array<{ allocated_amount: string; status: string }>;
      returns: Array<{ id: string; total: string }>;
      refunds: Array<{ amount: string; status: string }>;
      accounting_entries: Array<{ id: string; source_type: string; source_id: string; entry_role: string; currency_code: string; status: string }>;
    };
    expect(detail.id).toBe(firstSale.id);
    expect(detail.lines).toHaveLength(3);
    expect(detail.payments.filter(x => x.status === 'RECORDED').reduce((sum, row) => sum + Number(row.allocated_amount), 0)).toBe(Number(data.expected_paid));
    // The commerce response exposes only the journal headers linked to this sale;
    // cashiers cannot read the finance ledger directly. Verify the link and posting
    // state here, then verify journal line balance in the manager acceptance below.
    const saleJournal = detail.accounting_entries.find(x => x.source_type === 'SALE' && x.source_id === firstSale.id && x.entry_role === 'SALE_RECOGNITION');
    expect(saleJournal, 'sale revenue recognition journal is linked to the completed sale').toBeTruthy();
    expect(saleJournal!.status).toBe('POSTED');
    const paymentJournals = detail.accounting_entries.filter(x => x.source_type === 'PAYMENT' && x.entry_role === 'PAYMENT_RECEIPT');
    expect(paymentJournals.length).toBe(2);
    expect([...detail.accounting_entries].every(x => x.currency_code === data.currency_code), 'all linked journals use the sale currency').toBe(true);
    expect([...detail.accounting_entries].every(x => x.status === 'POSTED'), 'all linked journal entries are posted').toBe(true);

    for (const line of data.lines) {
      const after = await readBalance(page, data.location_id, line.variant_id);
      expect(after).toBe(Number((balancesBefore.get(line.variant_id)! - Number(line.quantity)).toFixed(4)));
      const { response, body } = await getJson(page, `/inventory/ledger?limit=500&location_id=${encodeURIComponent(data.location_id)}&variant_id=${encodeURIComponent(line.variant_id)}&transaction_type=SALE`);
      expect(response.status()).toBe(200);
      expect((body as Array<{ reference_id?: string | null; reference_type?: string | null }>).some(row => row.reference_type === 'sale' && row.reference_id === firstSale.id)).toBe(true);
    }

    // The fixture deliberately prices line 1 at 8,000 and line 2 at 3,000,
    // with 10,000 collected on a 15,000 sale. After refunding 8,000, the next
    // 3,000 refund must be rejected because only 2,000 of original collections remain.
    const returnChannel = data.payments[0].payment_channel_id;
    const lineForRefund = detail.lines.find(line => line.product_variant_id === data.lines[0].variant_id);
    const lineForOverRefund = detail.lines.find(line => line.product_variant_id === data.lines[1].variant_id);
    expect(lineForRefund).toBeTruthy();
    expect(lineForOverRefund).toBeTruthy();
    const returnBody = (saleLineId: string, reason: string) => ({
      reason,
      inventory_location_id: data.location_id,
      business_date: data.business_date,
      settlement_type: 'REFUND',
      refund_channel_id: returnChannel,
      lines: [{ sale_line_id: saleLineId, quantity: '1' }],
    });
    const firstReturn = await page.request.post(`${apiRoot}/commerce/sales/${firstSale.id}/returns`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() },
      data: returnBody(lineForRefund!.sale_line_id, 'Phase 5 acceptance first refund'),
    });
    expect(firstReturn.status(), 'first refund of 8,000 should be accepted').toBe(201);

    const overRefund = await page.request.post(`${apiRoot}/commerce/sales/${firstSale.id}/returns`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() },
      data: returnBody(lineForOverRefund!.sale_line_id, 'Phase 5 acceptance cumulative refund cap'),
    });
    expect(overRefund.status(), 'cumulative refund cannot exceed amount collected').toBe(422);
    expect(JSON.stringify(await overRefund.json())).toContain('remaining collected amount');

    const finalDetailRead = await getJson(page, `/commerce/sales/${firstSale.id}`);
    expect(finalDetailRead.response.status()).toBe(200);
    const finalDetail = finalDetailRead.body as { returns: Array<{ total: string }>; refunds: Array<{ amount: string; status: string }> };
    expect(finalDetail.returns.length).toBe(1);
    expect(finalDetail.refunds.filter(x => x.status === 'RECORDED').reduce((sum, row) => sum + Number(row.amount), 0)).toBe(8000);
  });

  test('cashier cannot override catalogue price or apply a discount', async ({ page }) => {
    const data = fixture!;
    expect(data.actor_role).toBe('cashier');
    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const dashboardRequest = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/commerce/dashboard') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/sales');
    await dashboardRequest;
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated cashier session supplied its API bearer token').toBe(true);
    const payload = {
      customer_party_id: data.customer_party_id,
      branch_id: data.branch_id,
      location_id: data.location_id,
      currency_code: data.currency_code,
      business_date: data.business_date,
      lines: data.lines.map(line => ({ ...line })),
      payments: data.payments.map(payment => ({ ...payment })),
    };
    const priceOverride = structuredClone(payload);
    priceOverride.lines[0].unit_price = String(Number(priceOverride.lines[0].unit_price) + 1);
    const priceResponse = await page.request.post(`${apiRoot}/commerce/sales`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() }, data: priceOverride,
    });
    expect(priceResponse.status(), 'cashier price override is forbidden').toBe(403);
    expect(JSON.stringify(await priceResponse.json())).toContain('Price override permission required');

    const discountPayload = structuredClone(payload);
    discountPayload.lines[0] = { ...discountPayload.lines[0], discount_amount: '1' } as typeof discountPayload.lines[0];
    const discountResponse = await page.request.post(`${apiRoot}/commerce/sales`, {
      headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() }, data: discountPayload,
    });
    expect(discountResponse.status(), 'cashier discount is forbidden').toBe(403);
    expect(JSON.stringify(await discountResponse.json())).toContain('Discount permission required');
  });

  test('manager can override configured price and apply an authorized discount', async ({ browser }) => {
    const managerStorage = process.env.LEXA_PHASE5_MANAGER_STORAGE_STATE;
    test.skip(!managerStorage, 'Provide a separate non-production manager storage-state file to exercise positive pricing/discount permissions.');
    const data = fixture!;
    liveAuthHeader = '';
    const context = await browser.newContext({ storageState: managerStorage! });
    try {
      const page = await context.newPage();
      page.on('request', request => {
        const authorization = request.headers()['authorization'];
        if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
      });
      const dashboardRequest = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/commerce/dashboard') && response.status() === 200, { timeout: 20_000 });
      await page.goto(new URL('/sales', baseUrl).toString());
      await dashboardRequest;
      const payload = {
        customer_party_id: data.customer_party_id,
        branch_id: data.branch_id,
        location_id: data.location_id,
        currency_code: data.currency_code,
        business_date: data.business_date,
        lines: [{ variant_id: data.lines[0].variant_id, quantity: '1', unit_price: '8001', discount_amount: '1', tax_rate: '0' }],
        payments: [{ payment_channel_id: data.payments[0].payment_channel_id, amount: '8000' }],
      };
      const response = await page.request.post(`${apiRoot}/commerce/sales`, {
        headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() },
        data: payload,
      });
      expect(response.status(), 'manager with pricing and sales permissions can post approved override/discount').toBe(201);
      const body = await response.json() as { id: string; total: string; amount_paid: string; amount_due: string };
      expect(Number(body.total)).toBe(8000);
      expect(Number(body.amount_paid)).toBe(8000);
      expect(Number(body.amount_due)).toBe(0);

      const detailRead = await getJson(page, `/commerce/sales/${body.id}`);
      expect(detailRead.response.status()).toBe(200);
      const detail = detailRead.body as { accounting_entries: Array<{ id: string; source_type: string; source_id: string; entry_role: string; currency_code: string; status: string }> };
      const saleEntries = detail.accounting_entries.filter(entry => entry.source_type === 'SALE' && entry.source_id === body.id && entry.entry_role === 'SALE_RECOGNITION');
      expect(saleEntries).toHaveLength(1);
      const eligibleEntries = detail.accounting_entries.filter(entry => entry.source_type === 'SALE' && entry.source_id === body.id);
      expect(eligibleEntries.length).toBeGreaterThanOrEqual(1);
      for (const header of eligibleEntries) {
        expect(header.currency_code).toBe(data.currency_code);
        expect(header.status).toBe('POSTED');
        const full = await getJson(page, `/accounting/journal-entries/${header.id}`);
        expect(full.response.status(), `journal ${header.id} is readable to the manager`).toBe(200);
        const journal = full.body as { entry: { status: string; currency_code: string }; lines: Array<{ debit: string; credit: string; currency_code: string }> };
        expect(journal.entry.status).toBe('POSTED');
        expect(journal.entry.currency_code).toBe(data.currency_code);
        expect(journal.lines.length).toBeGreaterThanOrEqual(2);
        expect(journal.lines.every(line => line.currency_code === data.currency_code), 'every journal line uses the journal currency').toBe(true);
        const debit = journal.lines.reduce((sum, line) => sum + Number(line.debit), 0);
        const credit = journal.lines.reduce((sum, line) => sum + Number(line.credit), 0);
        expect(debit).toBeCloseTo(credit, 4);
      }
    } finally {
      await context.close();
    }
  });

  test('manager cannot read or return a sale from an unassigned branch', async ({ browser }) => {
    const managerStorage = process.env.LEXA_PHASE5_MANAGER_STORAGE_STATE;
    const data = fixture!;
    test.skip(!managerStorage, 'Provide a non-production manager storage-state file to test cross-branch authorization.');
    test.skip(!data.cross_branch_sale_id, 'Seed a sale in a different branch and set cross_branch_sale_id in the staging fixture.');
    liveAuthHeader = '';
    const context = await browser.newContext({ storageState: managerStorage! });
    try {
      const page = await context.newPage();
      page.on('request', request => {
        const authorization = request.headers()['authorization'];
        if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
      });
      const dashboardRequest = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/commerce/dashboard') && response.status() === 200, { timeout: 20_000 });
      await page.goto(new URL('/sales', baseUrl).toString());
      await dashboardRequest;

      const detail = await page.request.get(`${apiRoot}/commerce/sales/${data.cross_branch_sale_id}`, { headers: authHeaders() });
      expect(detail.status(), 'sale detail must deny access to an unassigned branch').toBe(403);
      expect(JSON.stringify(await detail.json())).toContain('Access to this branch has not been assigned');

      const crossBranchReturn = await page.request.post(`${apiRoot}/commerce/sales/${data.cross_branch_sale_id}/returns`, {
        headers: { ...authHeaders(), 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() },
        data: {
          reason: 'Phase 5 cross-branch denial test',
          inventory_location_id: data.location_id,
          business_date: data.business_date,
          settlement_type: 'NONE',
          lines: [{ sale_line_id: data.cross_branch_sale_line_id || data.lines[0].variant_id, quantity: '1' }],
        },
      });
      expect(crossBranchReturn.status(), 'return creation must deny a sale from an unassigned branch').toBe(403);
      expect(JSON.stringify(await crossBranchReturn.json())).toContain('Access to this branch has not been assigned');

      const returns = await page.request.get(`${apiRoot}/commerce/returns`, { headers: authHeaders() });
      expect(returns.status(), 'assigned-branch manager can list accessible returns').toBe(200);
      if (data.cross_branch_return_id) {
        const rows = await returns.json() as Array<{ id: string }>;
        expect(rows.some(row => row.id === data.cross_branch_return_id), 'returns list must not leak records from unassigned branches').toBe(false);
      }
    } finally {
      await context.close();
    }
  });

});
