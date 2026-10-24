import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

type Fixture = {
  environment: 'staging'; disposable_scope: true; reset_strategy: 'dispose_test_tenant';
  actor_role: 'owner' | 'administrator'; branch_id: string; location_id: string;
  customer_party_id: string; variant_id: string; payment_channel_id: string;
  currency_code: string; business_date: string; unit_price: string; quantity: string;
  initial_payment: string; expected_total: string;
};
type SaleDetail = {
  id: string; status: string; total: string; amount_paid: string; amount_due: string;
  lines: Array<{ sale_line_id: string; product_variant_id: string }>;
  payments: Array<{ allocated_amount: string; status: string }>;
  accounting_entries: Array<{ id: string; source_type: string; source_id: string; entry_role: string; currency_code: string; status: string }>;
};
const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE2_ACCEPTANCE_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let host = '';
try { host = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { host = ''; }
const allowedHosts = (process.env.LEXA_PHASE2_STAGING_HOSTS || '').split(',').map(v => v.trim().toLowerCase()).filter(Boolean);
const productionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE2_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging' && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant' && !productionHosts.has(host)
  && allowedHosts.includes(host) && Boolean(process.env.LEXA_PHASE2_STORAGE_STATE);
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let authorization = '';
let api: import('@playwright/test').APIRequestContext;
function headers(idempotencyKey?: string) {
  return { ...(authorization ? { Authorization: authorization } : {}), ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}), 'X-Request-ID': randomUUID() };
}
function numeric(value: unknown): number {
  const n = Number(value);
  expect(Number.isFinite(n), 'saved monetary values must be finite numbers').toBe(true);
  return n;
}
async function get(path: string) {
  const response = await api.get(`${apiRoot}${path}`, { headers: headers() });
  return { response, body: await response.json().catch(() => null) as any };
}
async function post(path: string, body: unknown, key?: string) {
  const response = await api.post(`${apiRoot}${path}`, { headers: { ...headers(key), 'Content-Type': 'application/json' }, data: body });
  return { response, body: await response.json().catch(() => null) as any };
}
async function refresh(date: string) {
  const result = await post(`/analytics/refresh?start_date=${date}&end_date=${date}`, {});
  expect(result.response.status(), 'analytics refresh succeeds in staging').toBe(200);
  expect(result.body.status).toBe('SUCCEEDED');
}
async function metrics(date: string, currency: string) {
  const result = await get(`/analytics/overview?start_date=${date}&end_date=${date}&currency_code=${currency}`);
  expect(result.response.status()).toBe(200);
  return result.body as { totals: { sale_count: number; payments_collected: string | number } };
}

test.describe('Phase 2 completed sale → inventory → receivable → accounting → outbox → insights (staging only)', () => {
  test.skip(!explicitlySafe, 'Requires a disposable staging fixture, HTTPS host allow-list, QA storage state and LEXA_PHASE2_ALLOW_STAGING_WRITES=1.');

  test('idempotent checkout and credit settlement reconcile all connected modules', async ({ page, context }) => {
    const d = fixture!;
    const origin = new URL(baseUrl);
    expect(origin.protocol).toBe('https:');
    expect(['owner', 'administrator']).toContain(d.actor_role);
    expect(/^[A-Z]{3}$/.test(d.currency_code)).toBe(true);
    expect(numeric(d.quantity)).toBeGreaterThan(0);
    expect(numeric(d.unit_price)).toBeGreaterThan(0);
    expect(numeric(d.initial_payment)).toBeGreaterThan(0);
    expect(numeric(d.expected_total)).toBeGreaterThan(numeric(d.initial_payment));
    api = context.request;
    page.on('request', request => {
      const token = request.headers()['authorization'];
      if (token?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) authorization = token;
    });
    const dashboard = page.waitForResponse(r => r.url().includes('/api/lexa/api/v1/commerce/dashboard') && r.status() === 200, { timeout: 20_000 });
    await page.goto('/sales');
    await dashboard;
    expect(authorization.startsWith('Bearer ') || (await context.cookies(origin.origin)).length > 0, 'browser is authenticated to staging').toBe(true);

    const productsResult = await get('/commerce/products');
    expect(productsResult.response.status()).toBe(200);
    const product = (productsResult.body as Array<{ variant_id: string; selling_price: string; track_inventory: boolean }>).find(x => x.variant_id === d.variant_id);
    expect(product, 'seeded SKU must exist in the saved catalog').toBeTruthy();
    expect(numeric(product!.selling_price)).toBe(numeric(d.unit_price));
    expect(product!.track_inventory).toBe(true);

    const balPath = `/inventory/balances?limit=500&location_id=${encodeURIComponent(d.location_id)}&variant_id=${encodeURIComponent(d.variant_id)}`;
    const initialBalance = await get(balPath);
    expect(initialBalance.response.status()).toBe(200);
    const before = (initialBalance.body as Array<{ location_id: string; variant_id: string; on_hand: string; average_cost: string }>).find(x => x.location_id === d.location_id && x.variant_id === d.variant_id);
    expect(before, 'seeded SKU must have a materialized balance').toBeTruthy();
    const beforeStock = numeric(before!.on_hand);
    const averageCost = numeric(before!.average_cost);
    expect(beforeStock).toBeGreaterThanOrEqual(numeric(d.quantity));
    expect(averageCost).toBeGreaterThan(0);

    await refresh(d.business_date);
    const baseline = await metrics(d.business_date, d.currency_code);
    const payload = {
      customer_party_id: d.customer_party_id, branch_id: d.branch_id, location_id: d.location_id,
      currency_code: d.currency_code, business_date: d.business_date,
      notes: 'Disposable LEXA Phase 2 staging acceptance transaction.',
      lines: [{ variant_id: d.variant_id, quantity: d.quantity, unit_price: d.unit_price }],
      payments: [{ payment_channel_id: d.payment_channel_id, amount: d.initial_payment }],
    };
    const saleKey = randomUUID();
    const created = await post('/commerce/sales', payload, saleKey);
    expect(created.response.status(), 'staging checkout succeeds').toBe(201);
    const sale = created.body as { id: string; status: string; total: string; amount_paid: string; amount_due: string };
    expect(sale.id).toBeTruthy();
    expect(sale.status).toBe('COMPLETED');
    expect(numeric(sale.total)).toBe(numeric(d.expected_total));
    expect(numeric(sale.amount_paid)).toBe(numeric(d.initial_payment));
    expect(numeric(sale.amount_due)).toBeCloseTo(numeric(d.expected_total) - numeric(d.initial_payment), 4);
    const replay = await post('/commerce/sales', payload, saleKey);
    expect(replay.response.status()).toBe(201);
    expect(replay.body.id, 'same key returns the same sale, not a duplicate').toBe(sale.id);

    const detailResult = await get(`/commerce/sales/${encodeURIComponent(sale.id)}`);
    expect(detailResult.response.status()).toBe(200);
    const detail = detailResult.body as SaleDetail;
    const revenue = detail.accounting_entries.find(x => x.source_type === 'SALE' && x.source_id === sale.id && x.entry_role === 'SALE_RECOGNITION');
    const cogs = detail.accounting_entries.find(x => x.source_type === 'SALE' && x.source_id === sale.id && x.entry_role === 'COGS');
    expect(revenue, 'revenue/tax journal is linked to the sale').toBeTruthy();
    expect(cogs, 'cost of sales journal is linked to the valued inventory movement').toBeTruthy();
    for (const entry of [revenue!, cogs!]) {
      expect(entry.currency_code).toBe(d.currency_code);
      expect(entry.status).toBe('POSTED');
    }

    const ledger = await get(`/inventory/ledger?limit=500&location_id=${encodeURIComponent(d.location_id)}&variant_id=${encodeURIComponent(d.variant_id)}&transaction_type=SALE`);
    expect(ledger.response.status()).toBe(200);
    const movement = (ledger.body as Array<{ reference_type: string; reference_id: string; quantity_delta: string; unit_cost: string; total_cost: string }>).find(x => x.reference_type === 'sale' && x.reference_id === sale.id);
    expect(movement, 'inventory ledger records the sale').toBeTruthy();
    expect(numeric(movement!.quantity_delta)).toBeCloseTo(-numeric(d.quantity), 4);
    expect(numeric(movement!.unit_cost)).toBeCloseTo(averageCost, 4);
    expect(numeric(movement!.total_cost)).toBeGreaterThan(0);
    expect(numeric(movement!.total_cost)).toBeCloseTo(numeric(movement!.unit_cost) * numeric(d.quantity), 4);

    const openReceivables = await get('/commerce/receivables');
    expect(openReceivables.response.status()).toBe(200);
    const receivable = (openReceivables.body as Array<{ id: string; sale_id: string; balance: string }>).find(x => x.sale_id === sale.id);
    expect(receivable, 'partial checkout creates a receivable').toBeTruthy();
    expect(numeric(receivable!.balance)).toBeCloseTo(numeric(sale.amount_due), 4);
    const settlePayload = {
      amount: (numeric(d.expected_total) - numeric(d.initial_payment)).toFixed(4),
      payment_channel_id: d.payment_channel_id, business_date: d.business_date,
      reference: `P2-${randomUUID().slice(0, 8)}`,
    };
    const settleKey = randomUUID();
    const settled = await post(`/commerce/receivables/${encodeURIComponent(receivable!.id)}/payments`, settlePayload, settleKey);
    expect(settled.response.status()).toBe(201);
    expect(numeric(settled.body.balance)).toBe(0);
    const settleReplay = await post(`/commerce/receivables/${encodeURIComponent(receivable!.id)}/payments`, settlePayload, settleKey);
    expect(settleReplay.response.status()).toBe(201);
    expect(settleReplay.body.id).toBe(settled.body.id);

    const finalDetailResult = await get(`/commerce/sales/${encodeURIComponent(sale.id)}`);
    expect(finalDetailResult.response.status()).toBe(200);
    const finalDetail = finalDetailResult.body as SaleDetail;
    expect(numeric(finalDetail.amount_due)).toBe(0);
    expect(numeric(finalDetail.amount_paid)).toBeCloseTo(numeric(d.expected_total), 4);
    expect(finalDetail.payments.filter(x => x.status === 'RECORDED').reduce((sum, x) => sum + numeric(x.allocated_amount), 0)).toBeCloseTo(numeric(d.expected_total), 4);

    // Verify the actual journal lines, not only the headers attached to a sale.
    const postedEntries = finalDetail.accounting_entries.filter(entry =>
      (entry.source_type === 'SALE' && entry.source_id === sale.id) || entry.source_type === 'PAYMENT'
    );
    expect(postedEntries.some(entry => entry.source_type === 'SALE' && entry.source_id === sale.id && entry.entry_role === 'SALE_RECOGNITION')).toBe(true);
    expect(postedEntries.some(entry => entry.source_type === 'SALE' && entry.source_id === sale.id && entry.entry_role === 'COGS')).toBe(true);
    expect(postedEntries.filter(entry => entry.source_type === 'PAYMENT' && entry.entry_role === 'PAYMENT_RECEIPT').length).toBeGreaterThanOrEqual(2);
    for (const header of postedEntries) {
      expect(header.status).toBe('POSTED');
      expect(header.currency_code).toBe(d.currency_code);
      const journalResult = await get(`/accounting/journal-entries/${encodeURIComponent(header.id)}`);
      expect(journalResult.response.status(), `journal ${header.id} can be read in staging`).toBe(200);
      const journal = journalResult.body as { entry: { status: string; currency_code: string }; lines: Array<{ debit: string; credit: string; currency_code: string }> };
      expect(journal.entry.status).toBe('POSTED');
      expect(journal.entry.currency_code).toBe(d.currency_code);
      expect(journal.lines.length).toBeGreaterThanOrEqual(2);
      expect(journal.lines.every(line => line.currency_code === d.currency_code)).toBe(true);
      const debits = journal.lines.reduce((sum, line) => sum + numeric(line.debit), 0);
      const credits = journal.lines.reduce((sum, line) => sum + numeric(line.credit), 0);
      expect(debits).toBeCloseTo(credits, 4);
    }

    const finalBalance = await get(balPath);
    expect(finalBalance.response.status()).toBe(200);
    expect(numeric((finalBalance.body as Array<{ on_hand: string }>)[0]?.on_hand)).toBeCloseTo(beforeStock - numeric(d.quantity), 4);

    const evidenceResult = await get(`/commerce/sales/${encodeURIComponent(sale.id)}/evidence`);
    expect(evidenceResult.response.status()).toBe(200);
    const evidence = evidenceResult.body as { sale_id: string; sale_status: string; event_count: number; audit_count: number; successful_sale_idempotency_records: number; events: Array<{ event_type: string }> };
    expect(evidence.sale_id).toBe(sale.id);
    expect(evidence.sale_status).toBe('COMPLETED');
    expect(evidence.successful_sale_idempotency_records).toBe(1);
    expect(evidence.event_count).toBeGreaterThan(0);
    expect(evidence.audit_count).toBeGreaterThan(0);
    const eventTypes = new Set(evidence.events.map(x => x.event_type));
    for (const type of ['SALE_COMPLETED', 'STOCK_DECREASED', 'PAYMENT_RECORDED', 'PAYMENT_ALLOCATED', 'ACCOUNTING_ENTRY_POSTED', 'RECEIVABLE_CREATED']) {
      expect(eventTypes.has(type), `outbox includes ${type}`).toBe(true);
    }
    expect(JSON.stringify(evidence)).not.toMatch(/api[_-]?key|password|secret|customer_name|"payload"/i);

    await refresh(d.business_date);
    const finalMetrics = await metrics(d.business_date, d.currency_code);
    expect(Number(finalMetrics.totals.sale_count) - Number(baseline.totals.sale_count)).toBe(1);
    expect(numeric(finalMetrics.totals.payments_collected) - numeric(baseline.totals.payments_collected)).toBeCloseTo(numeric(d.expected_total), 4);
  });
});
