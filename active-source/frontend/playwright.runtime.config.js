import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: {
    timeout: 8_000,
  },
  fullyParallel: false,
  workers: 1,
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || 'test-results/pce-runtime-acceptance',
  reporter: [
    ['list'],
    ['html', { outputFolder: 'test-results/pce-runtime-html-report', open: 'never' }],
  ],
  use: {
    baseURL: process.env.PCE_BASE_URL || 'http://localhost:5173',
    browserName: 'chromium',
    channel: 'chrome',
    screenshot: 'only-on-failure',
    // Early golden-flow specs split traces manually at persisted checkpoints;
    // later runners own a single Playwright trace for their whole test.
    trace: process.env.PCE_MANUAL_CHECKPOINT_TRACE === '1'
      ? 'off'
      : process.env.PCE_GOLDEN_RUNNER_TRACE === '1' ? 'on' : 'retain-on-failure',
    video: 'off',
    viewport: { width: 1440, height: 960 },
    storageState: undefined,
    permissions: ['clipboard-read', 'clipboard-write'],
    userAgent: 'PCE-Runtime-Acceptance/V1.14.2.5',
  },
  projects: [
    {
      name: 'pce-runtime-chrome',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
      },
    },
  ],
})
