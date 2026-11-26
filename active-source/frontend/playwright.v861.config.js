import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'supplierSettlementCanaryV861.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 12_000 },
  use: {
    baseURL: 'http://localhost:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1600, height: 1000 },
    trace: 'on',
    screenshot: 'on',
  },
  outputDir: 'test-results/supplier-settlement-canary-v861/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/supplier-settlement-canary-v861/playwright-report.json' }],
  ],
})
