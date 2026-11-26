import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  outputDir: 'test-results/payment-instruction-prepare-v49/playwright-output',
  timeout: 300_000,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL: 'http://localhost:5173',
    channel: 'chrome',
    trace: 'on',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 960 },
  },
})
