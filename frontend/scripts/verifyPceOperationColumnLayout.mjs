import { runPlaywrightWithDevServer } from './pcePlaywrightRunner.mjs'

const VERSION = 'V1.14.2.8.4.7.1'
process.env.PCE_TARGET_TABLE_IDS = 'payment-execution-prepare-list,incoming-inspections-main'

const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceOperationColumnLayout.spec.js',
], {
  warmupResources: [
    '/src/main.js',
    '/src/router/index.js',
    '/src/meta/pages/QmsPage.vue',
    '/src/meta/pages/PaymentExecutionPreparePage.vue',
  ],
})

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)

if (result.error || result.status !== 0) {
  console.error(`${VERSION} operation column layout gate failed.`)
  if (result.error) console.error(result.error.message)
  process.exit(result.status || 1)
}

console.log(`${VERSION} operation column layout gate passed.`)
process.exit(0)
