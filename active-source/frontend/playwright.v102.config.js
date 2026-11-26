import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'pdeManufacturingOutputV102.spec.js',
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
  outputDir: 'test-results/pde-manufacturing-output-v102/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/pde-manufacturing-output-v102/playwright-report.json' }],
  ],
})
