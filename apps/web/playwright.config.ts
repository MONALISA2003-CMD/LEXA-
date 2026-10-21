import { defineConfig } from '@playwright/test';

const baseURL = process.env.LEXA_BROWSER_BASE_URL || 'http://127.0.0.1:3000';
const storageState = process.env.LEXA_PHASE7_STORAGE_STATE
  || process.env.LEXA_PHASE5_STORAGE_STATE
  || process.env.LEXA_PHASE4_STORAGE_STATE
  || { cookies: [], origins: [] };

export default defineConfig({
  testDir: './e2e',
  testMatch: /phase(5-sales|7-purchasing)-acceptance\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: process.env.LEXA_PHASE7_ALLOW_STAGING_WRITES === '1' ? 'test-results/phase7' : 'test-results/phase5',
  use: {
    baseURL,
    storageState,
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
