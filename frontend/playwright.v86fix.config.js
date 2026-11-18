import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/ui-baseline',
  testMatch: 'businessNavigationGovernanceV86Fix.spec.js',
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
  outputDir: 'test-results/business-navigation-governance-v86-fix/playwright-artifacts',
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/business-navigation-governance-v86-fix/playwright-report.json' }],
  ],
})
