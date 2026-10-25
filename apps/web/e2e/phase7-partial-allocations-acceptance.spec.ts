import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

type Fixture = {
  environment: 'staging';
  disposable_scope: true;
  reset_strategy: 'dispose_test_tenant';
  actor_role: 'owner' | 'administrator';
  supplier_party_id: string;
  currency_code: string;
  bill_a_id: string;
  bill_b_id: string;
  payment_amount: string;
  allocation_a: string;
  allocation_b: string;
};

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const rawFixture = process.env.LEXA_PHASE7_ALLOCATION_FIXTURE_JSON || '';
let fixture: Fixture | null = null;
try { fixture = rawFixture ? JSON.parse(rawFixture) as Fixture : null; } catch { fixture = null; }
let baseHost = '';
try { baseHost = baseUrl ? new URL(baseUrl).hostname.toLowerCase() : ''; } catch { baseHost = ''; }
const allowedHosts = (process.env.LEXA_PHASE7_STAGING_HOSTS || '').split(',').map(value => value.trim().toLowerCase()).filter(Boolean);
const storageState = process.env.LEXA_PHASE7_ALLOCATION_STORAGE_STATE || process.env.LEXA_PHASE7_STORAGE_STATE || '';
test.use({ storageState: storageState || { cookies: [], origins: [] } });
const productionHosts = new Set(['lexa-green.vercel.app', 'lexa-n10e.onrender.com']);
const explicitlySafe = process.env.LEXA_PHASE7_ALLOCATION_ALLOW_STAGING_WRITES === '1'
  && fixture?.environment === 'staging'
  && fixture?.disposable_scope === true
  && fixture?.reset_strategy === 'dispose_test_tenant'
  && ['owner', 'administrator'].includes(fixture?.actor_role || '')
  && !productionHosts.has(baseHost)
  && allowedHosts.includes(baseHost)
  && Boolean(storageState)
  && Boolean(fixture?.supplier_party_id && fixture?.currency_code && fixture?.bill_a_id && fixture?.bill_b_id)
  && Boolean(fixture?.payment_amount && fixture?.allocation_a && fixture?.allocation_b);
const apiRoot = `${baseUrl.replace(/\/$/, '')}/api/lexa/api/v1`;
let liveAuthHeader = '';
function authHeaders() { return liveAuthHeader ? { Authorization: liveAuthHeader } : {}; }

type Reply = { response: import('@playwright/test').APIResponse; body: any };
async function requestJson(page: import('@playwright/test').Page, method: 'GET' | 'POST', path: string, data?: unknown, key?: string): Promise<Reply> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (method === 'POST') headers['Content-Type'] = 'application/json';
  if (key) headers['Idempotency-Key'] = key;
  const response = method === 'GET'
    ? await page.request.get(`${apiRoot}${path}`, { headers })
    : await page.request.post(`${apiRoot}${path}`, { headers, data: data ?? {} });
  return { response, body: await response.json().catch(() => null) };
}
function amount(value: unknown, label: string): number {
  const result = Number(value);
  expect(Number.isFinite(result), `${label} must be numeric`).toBe(true);
  return result;
}
function close(actual: number, expected: number, label: string) {
  expect(Math.abs(actual - expected), `${label} must reconcile to the cent`).toBeLessThanOrEqual(0.01);
}

test.describe('Phase 7 partial supplier payment allocations (isolated staging only)', () => {
  test.skip(!explicitlySafe, 'Requires owner/admin QA auth, an explicit staging allow-list, two posted supplier bills, and a disposable tenant fixture.');

  test('partially allocates one payment to two bills, preserves the unapplied advance, and reconciles', async ({ page }) => {
    const data = fixture!;
    expect(new URL(baseUrl).protocol).toBe('https:');
    expect(/^[A-Z]{3}$/.test(data.currency_code)).toBe(true);
    const paymentAmount = amount(data.payment_amount, 'payment amount');
    const allocationA = amount(data.allocation_a, 'first allocation');
    const allocationB = amount(data.allocation_b, 'second allocation');
    const allocated = allocationA + allocationB;
    expect(allocationA).toBeGreaterThan(0);
    expect(allocationB).toBeGreaterThan(0);
    expect(paymentAmount).toBeGreaterThan(allocated);

    page.on('request', request => {
      const authorization = request.headers()['authorization'];
      if (authorization?.startsWith('Bearer ') && request.url().includes('/api/lexa/api/v1/')) liveAuthHeader = authorization;
    });
    const ready = page.waitForResponse(response => response.url().includes('/api/lexa/api/v1/purchasing/summary') && response.status() === 200, { timeout: 20_000 });
    await page.goto('/purchasing');
    await ready;
    expect(liveAuthHeader.startsWith('Bearer '), 'workspace session must supply a bearer token').toBe(true);

    const billQuery = new URLSearchParams({ status: 'POSTED', supplier_party_id: data.supplier_party_id, limit: '500' });
    const beforeBills = await requestJson(page, 'GET', `/purchasing/supplier-bills?${billQuery}`);
    expect(beforeBills.response.status(), JSON.stringify(beforeBills.body)).toBe(200);
    const bills = beforeBills.body as Array<Record<string, any>>;
    const billA = bills.find(row => String(row.id) === data.bill_a_id);
    const billB = bills.find(row => String(row.id) === data.bill_b_id);
    expect(billA, 'first fixture bill is posted and belongs to the supplier').toBeTruthy();
    expect(billB, 'second fixture bill is posted and belongs to the supplier').toBeTruthy();
    expect(billA!.currency_code).toBe(data.currency_code);
    expect(billB!.currency_code).toBe(data.currency_code);
    const openA = amount(billA!.allocated_outstanding, 'first bill outstanding');
    const openB = amount(billB!.allocated_outstanding, 'second bill outstanding');
    expect(allocationA, 'the first allocation must be partial, not full settlement').toBeLessThan(openA);
    expect(allocationB, 'the second allocation must be partial, not full settlement').toBeLessThan(openB);

    const beforeBalance = await requestJson(page, 'GET', `/purchasing/supplier-balances?supplier_party_id=${encodeURIComponent(data.supplier_party_id)}&currency_code=${encodeURIComponent(data.currency_code)}&include_zero=true`);
    expect(beforeBalance.response.status()).toBe(200);
    const initialBalance = (beforeBalance.body as Array<Record<string, any>>).find(row => row.supplier_party_id === data.supplier_party_id && row.currency_code === data.currency_code);
    expect(initialBalance, 'supplier ledger balance exists for the fixture').toBeTruthy();
    const initialNet = amount(initialBalance!.net_balance, 'initial net supplier balance');
    const initialEntries = amount(initialBalance!.entry_count, 'initial supplier ledger entry count');

    const token = randomUUID().replaceAll('-', '').slice(0, 12).toUpperCase();
    const paymentKey = `phase7-partial-payment-create-${token}`;
    const paymentPayload = {
      supplier_party_id: data.supplier_party_id,
      payment_number: `P7-ALLOC-${token}`,
      payment_date: new Date().toISOString().slice(0, 10),
      currency_code: data.currency_code,
      amount: paymentAmount.toFixed(2),
      payment_method: 'BANK_TRANSFER',
      reference: `P7-ALLOC-REF-${token}`,
      notes: 'Disposable staging acceptance: two partial bill allocations and retained supplier advance.',
      allocations: [
        { bill_id: data.bill_a_id, amount: allocationA.toFixed(2) },
        { bill_id: data.bill_b_id, amount: allocationB.toFixed(2) },
      ],
    };
    const created = await requestJson(page, 'POST', '/purchasing/supplier-payments', paymentPayload, paymentKey);
    expect(created.response.status(), JSON.stringify(created.body)).toBe(200);
    expect(created.body.status).toBe('DRAFT');
    close(amount(created.body.allocated_amount, 'allocated sum'), allocated, 'allocated sum');
    close(amount(created.body.unallocated_amount, 'unapplied amount'), paymentAmount - allocated, 'unapplied amount');

    const replayCreate = await requestJson(page, 'POST', '/purchasing/supplier-payments', paymentPayload, paymentKey);
    expect(replayCreate.response.status(), JSON.stringify(replayCreate.body)).toBe(200);
    expect(replayCreate.body.id).toBe(created.body.id);

    const paymentId = String(created.body.id);
    const postingKey = `phase7-partial-payment-post-${token}`;
    const posted = await requestJson(page, 'POST', `/purchasing/supplier-payments/${encodeURIComponent(paymentId)}/post`, {}, postingKey);
    expect(posted.response.status(), JSON.stringify(posted.body)).toBe(200);
    expect(posted.body.status).toBe('POSTED');
    close(amount(posted.body.allocated_amount, 'posted allocation'), allocated, 'posted allocation');
    close(amount(posted.body.advance_amount, 'supplier advance'), paymentAmount - allocated, 'supplier advance');
    const replayPost = await requestJson(page, 'POST', `/purchasing/supplier-payments/${encodeURIComponent(paymentId)}/post`, {}, postingKey);
    expect(replayPost.response.status(), JSON.stringify(replayPost.body)).toBe(200);
    expect(replayPost.body.id).toBe(paymentId);

    const afterBillsReply = await requestJson(page, 'GET', `/purchasing/supplier-bills?${billQuery}`);
    expect(afterBillsReply.response.status()).toBe(200);
    const afterBills = afterBillsReply.body as Array<Record<string, any>>;
    const afterA = afterBills.find(row => String(row.id) === data.bill_a_id)!;
    const afterB = afterBills.find(row => String(row.id) === data.bill_b_id)!;
    close(openA - amount(afterA.allocated_outstanding, 'first bill after allocation'), allocationA, 'first bill payment allocation');
    close(openB - amount(afterB.allocated_outstanding, 'second bill after allocation'), allocationB, 'second bill payment allocation');

    const afterBalanceReply = await requestJson(page, 'GET', `/purchasing/supplier-balances?supplier_party_id=${encodeURIComponent(data.supplier_party_id)}&currency_code=${encodeURIComponent(data.currency_code)}&include_zero=true`);
    expect(afterBalanceReply.response.status()).toBe(200);
    const finalBalance = (afterBalanceReply.body as Array<Record<string, any>>).find(row => row.supplier_party_id === data.supplier_party_id && row.currency_code === data.currency_code)!;
    close(initialNet - amount(finalBalance.net_balance, 'final net supplier balance'), paymentAmount, 'supplier subledger net movement');
    expect(amount(finalBalance.entry_count, 'final supplier ledger entry count')).toBe(initialEntries + 1);

    const ledgerReply = await requestJson(page, 'GET', `/purchasing/supplier-ledger/${encodeURIComponent(data.supplier_party_id)}?currency_code=${encodeURIComponent(data.currency_code)}&limit=1000`);
    expect(ledgerReply.response.status()).toBe(200);
    const ledger = ledgerReply.body as Array<Record<string, any>>;
    const paymentEntries = ledger.filter(row => row.entry_type === 'PAYMENT' && row.source_id === paymentId);
    expect(paymentEntries, 'payment posts exactly one immutable supplier ledger entry').toHaveLength(1);
    close(amount(paymentEntries[0].credit_amount, 'supplier ledger payment credit'), paymentAmount, 'supplier ledger payment credit');

    const reconciliation = await requestJson(page, 'GET', '/purchasing/reconciliation');
    expect(reconciliation.response.status(), JSON.stringify(reconciliation.body)).toBe(200);
    expect(reconciliation.body.checks.supplier_ledger_entries_missing_journals).toBe(0);
    expect(reconciliation.body.checks.unbalanced_posted_journals).toBe(0);
    expect(reconciliation.body.checks.supplier_subledger_gl_mismatches).toBe(0);
  });
});
