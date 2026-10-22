import { expect, test } from '@playwright/test';

const baseUrl = process.env.LEXA_BROWSER_BASE_URL || '';
const storageState = process.env.LEXA_PHASE8_STORAGE_STATE || '';
const permittedHosts = (process.env.LEXA_PHASE8_STAGING_HOSTS || '')
  .split(',').map(value => value.trim().toLowerCase()).filter(Boolean);
let hostname = '';
try { hostname = new URL(baseUrl).hostname.toLowerCase(); } catch { hostname = ''; }
const explicitlySafe = process.env.LEXA_PHASE8_ALLOW_STAGING_READS === '1'
  && Boolean(storageState)
  && permittedHosts.includes(hostname);

test.describe('Stage 4 reporting and Stage 5 browser acceptance (read-only)', () => {
  test.skip(!explicitlySafe, 'Requires an authenticated QA storage state, explicit read-only staging opt-in, and an allow-listed staging hostname.');

  test('reports apply a date preset, export records, and preserve a usable mobile layout', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setViewportSize({ width: 390, height: 844 });
    const response = await page.goto('/reports');
    expect(response, 'reports navigation should return a document').not.toBeNull();
    expect(response!.status()).toBeLessThan(400);
    await expect(page.getByRole('heading', { name: 'Business reports' })).toBeVisible();
    await expect(page.getByRole('group', { name: 'Common reporting periods' })).toBeVisible();
    await page.getByRole('button', { name: 'Last 7 days' }).click();
    await expect(page.getByText(/Showing \d{4}-\d{2}-\d{2} through \d{4}-\d{2}-\d{2}/)).toBeVisible({ timeout: 20_000 });

    const exportButton = page.getByRole('button', { name: 'Download report (CSV)' });
    await expect(exportButton).toBeEnabled({ timeout: 20_000 });
    const downloadPromise = page.waitForEvent('download');
    await exportButton.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^lexa-business-reports-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.csv$/);

    const dimensions = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scroll, 'reports page should not overflow on mobile').toBeLessThanOrEqual(dimensions.client + 1);
    expect(pageErrors, 'browser runtime errors should be absent').toEqual([]);
  });

  test('core business pages open without failed required data requests', async ({ page }) => {
    const pages = [
      { path: '/', heading: 'Business overview' },
      { path: '/sales', heading: 'Sales' },
      { path: '/inventory', heading: 'Inventory' },
      { path: '/products', heading: 'Products' },
      { path: '/customers', heading: 'Customers' },
      { path: '/purchasing', heading: 'Purchases' },
      { path: '/accounting', heading: 'Finance' },
      { path: '/reports', heading: 'Business reports' },
    ];
    for (const item of pages) {
      const failures: string[] = [];
      const pageErrors: string[] = [];
      const onResponse = (response: import('@playwright/test').Response) => {
        const url = response.url();
        if (!url.includes('/api/v1/')) return;
        if (response.status() >= 500 || [401, 403].includes(response.status())) {
          failures.push(`${response.status()} ${new URL(url).pathname}`);
        }
      };
      const onPageError = (error: Error) => pageErrors.push(error.message);
      page.on('response', onResponse);
      page.on('pageerror', onPageError);
      try {
        const response = await page.goto(item.path);
        expect(response, `${item.path} should return a page`).not.toBeNull();
        expect(response!.status(), `${item.path} document status`).toBeLessThan(400);
        await expect(page.getByRole('heading', { name: item.heading, exact: true }), `${item.path} heading`).toBeVisible();
        await page.waitForLoadState('networkidle', { timeout: 7000 }).catch(() => undefined);
        expect(failures, `${item.path} API access errors`).toEqual([]);
        expect(pageErrors, `${item.path} browser errors`).toEqual([]);
      } finally {
        page.off('response', onResponse);
        page.off('pageerror', onPageError);
      }
    }
  });

  test('report links open sales history with their date and payment filters', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/reports');
    await expect(page.getByRole('heading', { name: 'Business reports' })).toBeVisible();
    await page.getByRole('button', { name: 'Last 30 days' }).click();
    await expect(page.getByText(/Showing \d{4}-\d{2}-\d{2} through \d{4}-\d{2}-\d{2}/)).toBeVisible({ timeout: 20_000 });
    const paymentLink = page.locator('table a[href*="payment_channel_id="]').first();
    if (await paymentLink.count()) {
      await paymentLink.click();
      await expect(page).toHaveURL(/\/sales\?view=history&start_date=\d{4}-\d{2}-\d{2}&end_date=\d{4}-\d{2}-\d{2}.*payment_channel_id=/);
      await expect(page.getByRole('button', { name: 'Past sales' })).toHaveClass(/selected/);
      await expect(page.getByLabel('Payment method')).toBeVisible();
    } else {
      await expect(page.getByText(/No customer payments were recorded in this period/)).toBeVisible();
    }
  });
});
