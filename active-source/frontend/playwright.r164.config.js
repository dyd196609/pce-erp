import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/auth',
  testMatch: 'purchaseRequestDraftRefreshR164.spec.js',
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://localhost:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1800, height: 1100 },
    trace: 'on',
    screenshot: 'only-on-failure',
  },
  outputDir: 'test-results/purchase-request-draft-refresh-r164/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/purchase-request-draft-refresh-r164/playwright-report.json' }],
  ],
})
