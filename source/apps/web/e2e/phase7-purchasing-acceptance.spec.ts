import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'owner' | 'administrator' | 'manager' | 'finance';
  branch_id: string;
  location_id: string;
  variant_id: string;
  currency_code: string;
  unit_cost: string;
  order_quantity: string;
  receipt_quantity: string;
  landed_cost_amount: string;
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE7_ACCEPTANCE_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const stagingHosts = (process.env.LEXA_PHASE7_STAGING_HOSTS || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
const storageState = process.env.LEXA_PHASE7_STORAGE_STATE || process.env.LEXA_PHASE5_STORAGE_STATE || process.env.LEXA_PHASE4_STORAGE_STATE || '';
const knownProductionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE7_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && !knownProductionHosts.has(baseHost)
  && stagingHosts.includes(baseHost)
  && Boolean(storageState)
  && fixture?.actor_role !== undefined;
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
  const body = await response.json().catch(() => null);
  return { response, body };
}

async function readBalance(page: import('@playwright/test').Page, locationId: string, variantId: string) {
  const { response, body } = await requestJson(page, 'GET', `/inventory/balances?limit=500&location_id=${encodeURIComponent(locationId)}&variant_id=${encodeURIComponent(variantId)}`);
  expect(response.status(), 'inventory balance read succeeds').toBe(200);
  const row = (body as Array<{ location_id: string; variant_id: string; on_hand: string }>).find(x => x.location_id === locationId && x.variant_id === variantId);
  expect(row, `inventory balance exists for ${variantId} at ${locationId}`).toBeTruthy();
  return Number(row!.on_hand);
}

// This end-to-end scenario posts supplier, inventory and payable mutations.
// It is skipped unless a specific staging hostname, temporary fixture, separate
// authenticated QA storage state and explicit write opt-in are all supplied.
test.describe('Phase 7 authenticated purchasing acceptance (isolated staging only)', () => {
  test.skip(!explicitlySafe, 'Requires a staging hostname allow-list, disposable fixture, authenticated QA storage state and LEXA_PHASE7_ALLOW_STAGING_WRITES=1.');

  test('supplier → approved order → partial receipt + landed cost → matched supplier bill → payment → supplier return and balances', async ({ page }) => {
    const data = fixture!;
    expect(['owner', 'administrator', 'manager', 'finance']).toContain(data.actor_role);
    expect(new URL(baseUrl).hostname.toLowerCase()).toBe(baseHost);
    expect(Number(data.unit_cost)).toBeGreaterThan(0);
    expect(Number(data.order_quantity)).toBeGreaterThan(Number(data.receipt_quantity));
    expect(Number(data.receipt_quantity)).toBeGreaterThan(0);
    expect(Number(data.landed_cost_amount)).toBeGreaterThan(0);
    expect(/^[A-Z]{3}$/.test(data.currency_code)).toBe(true);

    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const summaryWait = page.waitForResponse(r => r.url().includes('/api/lexa/api/v1/purchasing/summary') && r.status() === 200, { timeout: 20_000 });
    await page.goto('/purchasing');
    await summaryWait;
    await expect(page.getByText('Purchasing & supplier management')).toBeVisible();
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated staging browser supplied a bearer token').toBe(true);

    const before = await readBalance(page, data.location_id, data.variant_id);
    const token = randomUUID().replaceAll('-', '').slice(0, 10).toUpperCase();
    const supplierPayload = {
      name: `Phase 7 Acceptance Supplier ${token}`,
      code: `P7-${token}`,
      currency_code: data.currency_code,
      payment_terms_days: 30,
      default_receiving_location_id: data.location_id,
      notes: 'Disposable seeded Phase 7 E2E supplier; safe to delete with staging reset.',
    };
    const supplierKey = randomUUID();
    const supplierResult = await requestJson(page, 'POST', '/purchasing/suppliers', supplierPayload, supplierKey);
    expect(supplierResult.response.status(), 'supplier can be created').toBe(200);
    const supplier = supplierResult.body as { supplier_party_id: string; name: string };
    expect(supplier.supplier_party_id).toBeTruthy();
    const supplierReplay = await requestJson(page, 'POST', '/purchasing/suppliers', supplierPayload, supplierKey);
    expect(supplierReplay.response.status(), 'idempotent supplier retry returns a valid response').toBe(200);
    expect((supplierReplay.body as { supplier_party_id: string }).supplier_party_id).toBe(supplier.supplier_party_id);

    const order = await requestJson(page, 'POST', '/purchasing/purchase-orders', {
      supplier_party_id: supplier.supplier_party_id,
      branch_id: data.branch_id,
      receiving_location_id: data.location_id,
      order_date: new Date().toISOString().slice(0, 10),
      currency_code: data.currency_code,
      notes: 'Phase 7 E2E: one partially received tracked variant.',
      lines: [{ variant_id: data.variant_id, ordered_quantity: data.order_quantity, unit_cost: data.unit_cost, tax_rate: '0', description: 'Phase 7 acceptance item' }],
    });
    expect(order.response.status(), 'draft PO created').toBe(200);
    const po = order.body as { id: string; po_number: string };
    expect(po.id).toBeTruthy();
    const submitted = await requestJson(page, 'POST', `/purchasing/purchase-orders/${po.id}/submit`, { reason: 'Phase 7 acceptance submission' });
    expect(submitted.response.status()).toBe(200);
    expect((submitted.body as { status: string }).status).toBe('SUBMITTED');
    const approved = await requestJson(page, 'POST', `/purchasing/purchase-orders/${po.id}/approve`, { reason: 'Phase 7 acceptance approval' });
    expect(approved.response.status()).toBe(200);
    expect((approved.body as { status: string }).status).toBe('OPEN');

    const poDetailRead = await requestJson(page, 'GET', `/purchasing/purchase-orders/${po.id}`);
    expect(poDetailRead.response.status()).toBe(200);
    const poDetail = poDetailRead.body as { lines: Array<{ id: string; variant_id: string }> };
    expect(poDetail.lines).toHaveLength(1);
    const receipt = await requestJson(page, 'POST', `/purchasing/purchase-orders/${po.id}/receipts`, {
      notes: 'Phase 7 partial receiving acceptance',
      lines: [{ purchase_order_line_id: poDetail.lines[0].id, received_quantity: data.receipt_quantity, unit_cost: data.unit_cost, variance_reason: null, notes: 'Count checked' }],
      landed_costs: [{ cost_code: 'FREIGHT', description: 'Inbound freight acceptance fixture', amount: data.landed_cost_amount, currency_code: data.currency_code, allocation_method: 'BY_VALUE', reference: `FREIGHT-${token}` }],
    });
    expect(receipt.response.status(), 'draft goods receipt created').toBe(200);
    const receiptId = (receipt.body as { id: string }).id;
    const postedReceiptKey = randomUUID();
    const postedReceipt = await requestJson(page, 'POST', `/purchasing/receipts/${receiptId}/post`, undefined, postedReceiptKey);
    expect(postedReceipt.response.status(), 'receipt posting increases stock').toBe(200);
    expect((postedReceipt.body as { status: string }).status).toBe('POSTED');
    const receiptReplay = await requestJson(page, 'POST', `/purchasing/receipts/${receiptId}/post`, undefined, postedReceiptKey);
    expect(receiptReplay.response.status(), 'receipt retry replays the response instead of doubling stock').toBe(200);
    const afterReceipt = await readBalance(page, data.location_id, data.variant_id);
    expect(afterReceipt).toBe(Number((before + Number(data.receipt_quantity)).toFixed(6)));

    const goodsSubtotal = (Math.round(Number(data.unit_cost) * Number(data.receipt_quantity) * 100) / 100).toFixed(2);
    const bill = await requestJson(page, 'POST', '/purchasing/supplier-bills', {
      supplier_party_id: supplier.supplier_party_id,
      bill_number: `INV-${token}`,
      bill_date: new Date().toISOString().slice(0, 10),
      currency_code: data.currency_code,
      subtotal: goodsSubtotal,
      tax_amount: '0.00',
      other_charges: '0.00',
      purchase_order_id: po.id,
      purchase_receipt_id: receiptId,
      supplier_reference: `SUP-${token}`,
    });
    expect(bill.response.status(), 'receipt-linked supplier invoice created').toBe(200);
    const billId = (bill.body as { id: string; match_status: string }).id;
    expect((bill.body as { match_status: string }).match_status).toBe('MATCHED');
    const postBill = await requestJson(page, 'POST', `/purchasing/supplier-bills/${billId}/post`);
    expect(postBill.response.status(), 'matched supplier bill posts payable').toBe(200);

    const paymentAmount = goodsSubtotal;
    const payment = await requestJson(page, 'POST', '/purchasing/supplier-payments', {
      supplier_party_id: supplier.supplier_party_id,
      payment_number: `PAY-${token}`,
      payment_date: new Date().toISOString().slice(0, 10),
      currency_code: data.currency_code,
      amount: paymentAmount,
      payment_method: 'BANK_TRANSFER',
      reference: `BANK-${token}`,
      allocations: [{ bill_id: billId, amount: paymentAmount }],
    });
    expect(payment.response.status(), 'supplier payment draft created').toBe(200);
    const paymentId = (payment.body as { id: string }).id;
    const postedPayment = await requestJson(page, 'POST', `/purchasing/supplier-payments/${paymentId}/post`);
    expect(postedPayment.response.status(), 'supplier payment posts ledger credit').toBe(200);

    const receiptDetailRead = await requestJson(page, 'GET', `/purchasing/receipts/${receiptId}`);
    expect(receiptDetailRead.response.status()).toBe(200);
    const receiptDetail = receiptDetailRead.body as { lines: Array<{ id: string; received_quantity: string; base_unit_cost: string }> };
    const returnResult = await requestJson(page, 'POST', '/purchasing/returns', {
      purchase_receipt_id: receiptId,
      reason: 'Damaged goods in staging acceptance',
      notes: 'Automatically seeded, isolated staging-only return.',
      lines: [{ purchase_receipt_line_id: receiptDetail.lines[0].id, quantity: data.receipt_quantity, reason: 'Damaged acceptance fixture' }],
    });
    expect(returnResult.response.status(), 'supplier return request created').toBe(200);
    const returnId = (returnResult.body as { id: string }).id;
    expect((await requestJson(page, 'POST', `/purchasing/returns/${returnId}/approve`)).response.status()).toBe(200);
    expect((await requestJson(page, 'POST', `/purchasing/returns/${returnId}/post`)).response.status()).toBe(200);
    const afterReturn = await readBalance(page, data.location_id, data.variant_id);
    expect(afterReturn).toBe(before);

    const balances = await requestJson(page, 'GET', `/purchasing/supplier-balances?supplier_party_id=${encodeURIComponent(supplier.supplier_party_id)}&currency_code=${encodeURIComponent(data.currency_code)}&include_zero=true`);
    expect(balances.response.status()).toBe(200);
    expect((balances.body as Array<{ supplier_party_id: string; currency_code: string }>).some(x => x.supplier_party_id === supplier.supplier_party_id && x.currency_code === data.currency_code)).toBe(true);
    const ledger = await requestJson(page, 'GET', `/purchasing/supplier-ledger/${supplier.supplier_party_id}?currency_code=${encodeURIComponent(data.currency_code)}`);
    expect(ledger.response.status()).toBe(200);
    const entries = ledger.body as Array<{ entry_type: string }>;
    expect(entries.some(x => x.entry_type === 'BILL')).toBe(true);
    expect(entries.some(x => x.entry_type === 'PAYMENT')).toBe(true);
    expect(entries.some(x => x.entry_type === 'RETURN_CREDIT')).toBe(true);
  });

  test('supplier invoice linked to an order but not a posted receipt cannot post without a reviewed exception', async ({ page }) => {
    const data = fixture!;
    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const summaryWait = page.waitForResponse(r => r.url().includes('/api/lexa/api/v1/purchasing/summary') && r.status() === 200, { timeout: 20_000 });
    await page.goto('/purchasing');
    await summaryWait;
    await expect(page.getByText('Purchasing & supplier management')).toBeVisible();
    expect(liveAuthHeader.startsWith('Bearer '), 'authenticated staging browser supplied a bearer token').toBe(true);
    const requestAuth = await page.request.get(`${apiRoot}/purchasing/summary`, { headers: authHeaders() });
    expect(requestAuth.status()).toBe(200);
    // Use a newly created disposable supplier/order so this test cannot collide with the happy-path invoice.
    const token = randomUUID().replaceAll('-', '').slice(0, 10).toUpperCase();
    const supplier = await requestJson(page, 'POST', '/purchasing/suppliers', {
      name: `Phase 7 Pre-receipt ${token}`, code: `P7R-${token}`, currency_code: data.currency_code,
      payment_terms_days: 30, default_receiving_location_id: data.location_id,
    });
    expect(supplier.response.status()).toBe(200);
    const supplierId = (supplier.body as { supplier_party_id: string }).supplier_party_id;
    const order = await requestJson(page, 'POST', '/purchasing/purchase-orders', {
      supplier_party_id: supplierId, branch_id: data.branch_id, receiving_location_id: data.location_id,
      order_date: new Date().toISOString().slice(0, 10), currency_code: data.currency_code,
      lines: [{ variant_id: data.variant_id, ordered_quantity: data.order_quantity, unit_cost: data.unit_cost, tax_rate: '0' }],
    });
    expect(order.response.status()).toBe(200);
    const orderId = (order.body as { id: string }).id;
    expect((await requestJson(page, 'POST', `/purchasing/purchase-orders/${orderId}/submit`, { reason: 'Pre-receipt bill acceptance' })).response.status()).toBe(200);
    expect((await requestJson(page, 'POST', `/purchasing/purchase-orders/${orderId}/approve`, { reason: 'Pre-receipt bill acceptance' })).response.status()).toBe(200);
    const invoice = await requestJson(page, 'POST', '/purchasing/supplier-bills', {
      supplier_party_id: supplierId, bill_number: `EARLY-${token}`, bill_date: new Date().toISOString().slice(0, 10),
      currency_code: data.currency_code, subtotal: (Number(data.unit_cost) * Number(data.receipt_quantity)).toFixed(2),
      tax_amount: '0.00', other_charges: '0.00', purchase_order_id: orderId,
    });
    expect(invoice.response.status()).toBe(200);
    const invoiceBody = invoice.body as { id: string; match_status: string };
    expect(invoiceBody.match_status).toBe('WAITING_RECEIPT');
    const blocked = await requestJson(page, 'POST', `/purchasing/supplier-bills/${invoiceBody.id}/post`);
    expect(blocked.response.status(), 'unreceived linked invoice cannot post automatically').toBe(409);
    const override = await requestJson(page, 'POST', `/purchasing/supplier-bills/${invoiceBody.id}/accept-variance`, { reason: 'Supplier invoice intentionally precedes goods receipt; authorised advance exception.' });
    expect(override.response.status()).toBe(200);
    expect((override.body as { match_status: string }).match_status).toBe('OVERRIDDEN');
    expect((await requestJson(page, 'POST', `/purchasing/supplier-bills/${invoiceBody.id}/post`)).response.status()).toBe(200);
  });
});
