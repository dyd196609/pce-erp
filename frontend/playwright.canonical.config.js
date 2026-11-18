import path from 'node:path'
import { defineConfig } from '@playwright/test'
import runtimeConfig from './playwright.runtime.config.js'

const outputRoot = process.env.PCE_CANONICAL_OUTPUT_DIR
if (!outputRoot || !process.env.PCE_PLAYWRIGHT_RUN_ID) {
  throw new Error('Canonical output isolation requires npm run verify:pce-canonical-names; no shared-directory fallback is allowed.')
}
// Playwright gives this environment variable precedence over reporter options.
process.env.PLAYWRIGHT_HTML_OUTPUT_DIR = path.join(outputRoot, 'html')
process.env.PLAYWRIGHT_HTML_OPEN = 'never'

// The existing runner allocates this once; config/worker reloads reuse it.
export default defineConfig({
  ...runtimeConfig,
  outputDir: path.join(outputRoot, 'results'),
  preserveOutput: 'always',
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(outputRoot, 'html'), open: 'never' }],
  ],
})
