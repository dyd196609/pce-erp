export default {
  testDir: './tests',
  outputDir: 'test-results/purchase-canary-persistent-walkthrough/playwright-output',
  timeout: 60000,
  use: {
    baseURL: 'http://127.0.0.1:5174',
    headless: true,
    channel: 'chrome',
    trace: 'on',
  },
  webServer: {
    command: 'npm.cmd run dev -- --host 127.0.0.1 --port 5174',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      VITE_API_BASE_URL: 'http://127.0.0.1:8011',
    },
  },
}
