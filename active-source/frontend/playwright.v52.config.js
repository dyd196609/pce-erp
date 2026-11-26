import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  outputDir: 'test-results/payment-risk-review-v52/playwright-output',
  timeout: 300_000,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    channel: 'chrome',
    trace: 'on',
    screenshot: 'only-on-failure',
    viewport: { width: 1366, height: 768 },
  },
})

