import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'pceWebAcceptanceV503Strict.spec.js',
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  outputDir: 'test-results/pce-web-acceptance-v11-strict-golden-flow/playwright-output',
  reporter: [['list']],
  use: {
    baseURL: process.env.PCE_V503_BASE_URL || 'http://localhost:5173',
    browserName: 'chromium',
    channel: 'chrome',
    viewport: { width: 1366, height: 768 },
    trace: 'on',
    screenshot: 'off',
    video: 'off',
    permissions: ['clipboard-read', 'clipboard-write'],
  },
  projects: [{
    name: 'pce-v503-strict-chrome',
    use: { ...devices['Desktop Chrome'], channel: 'chrome' },
  }],
})
