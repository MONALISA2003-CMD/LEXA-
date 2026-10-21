import { expect, test } from '@playwright/test';

const publicRoutes = [
  '/', '/login', '/register', '/invite', '/products', '/inventory', '/sales',
  '/commerce', '/customers', '/purchasing', '/accounting', '/reports',
  '/compliance', '/intelligence', '/administration', '/settings',
];

test('application routes respond and render an application surface', async ({ page }) => {
  for (const route of publicRoutes) {
    const response = await page.goto(route);
    expect(response, `no document response for ${route}`).not.toBeNull();
    expect(response!.status(), `HTTP status for ${route}`).toBeLessThan(400);
    await expect(page.locator('body')).not.toBeEmpty();
    await expect(page.locator('body')).not.toContainText('Application error');
  }
});

test('product routes do not create horizontal overflow on mobile, tablet or desktop', async ({ page }) => {
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    for (const route of ['/', '/login', '/products', '/inventory', '/purchasing']) {
      await page.goto(route);
      const dimensions = await page.evaluate(() => ({
        client: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth,
      }));
      expect(dimensions.scroll, `${route} overflows at ${width}px`).toBeLessThanOrEqual(dimensions.client + 1);
    }
  }
});

test('login page exposes labelled email/password controls and keyboard focus', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByLabel(/email/i).first()).toBeVisible();
  await expect(page.getByLabel(/password/i).first()).toBeVisible();
  await page.keyboard.press('Tab');
  const focus = await page.evaluate(() => ({
    tag: document.activeElement?.tagName,
    visible: Boolean(document.activeElement && (document.activeElement as HTMLElement).getClientRects().length),
  }));
  expect(focus.visible).toBe(true);
});

test('keyboard users can reach an interactive control on the login page', async ({ page }) => {
  await page.goto('/login');
  let found = false;
  for (let i = 0; i < 20; i += 1) {
    await page.keyboard.press('Tab');
    found = await page.evaluate(() => {
      const node = document.activeElement as HTMLElement | null;
      if (!node) return false;
      const role = node.getAttribute('role');
      return ['BUTTON', 'INPUT', 'A', 'SELECT', 'TEXTAREA'].includes(node.tagName) || role === 'button' || role === 'link';
    });
    if (found) break;
  }
  expect(found).toBe(true);
});
