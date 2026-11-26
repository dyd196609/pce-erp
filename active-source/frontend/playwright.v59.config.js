import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'bankSendTaskV59.spec.js',
  outputDir: 'test-results/bank-send-task-v59/playwright-output',
  timeout: 180_000,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL: process.env.PCE_V59_WEB_BASE_URL
      || 'http://127.0.0.1:5173',
    channel: 'chrome',
    trace: 'on',
    screenshot: 'only-on-failure',
    viewport: { width: 1366, height: 768 },
  },
})
