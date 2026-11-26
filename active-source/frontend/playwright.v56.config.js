import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  outputDir:
    'test-results/payment-chain-legacy-governance-v56/playwright-output',
  timeout: 300_000,
  workers: 1,
  reporter: [['line']],
  use: {
    baseURL:
      process.env.PCE_V56_WEB_BASE_URL || 'http://127.0.0.1:5184',
    channel: 'chrome',
    trace: 'on',
    screenshot: 'only-on-failure',
    viewport: { width: 1366, height: 768 },
  },
})
