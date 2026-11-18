import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'bankSendTaskFactLoadV5911.spec.js',
  outputDir: 'test-results/bank-send-task-v5911/playwright-output',
  timeout: 180_000,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL: process.env.PCE_V5911_WEB_BASE_URL
      || 'http://localhost:5173',
    channel: 'chrome',
    trace: 'on',
    screenshot: 'on',
    viewport: { width: 1440, height: 900 },
  },
})
