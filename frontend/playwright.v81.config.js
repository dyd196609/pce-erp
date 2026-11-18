import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'supplierReconciliationPerformanceV81.spec.js',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1440, height: 900 },
    trace: 'on',
    screenshot: 'on',
  },
  outputDir: 'test-results/supplier-reconciliation-performance-v81/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/supplier-reconciliation-performance-v81/playwright-report.json' }],
  ],
})
