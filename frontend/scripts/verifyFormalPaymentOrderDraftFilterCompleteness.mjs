import { runPlaywrightWithDevServer } from './pcePlaywrightRunner.mjs'

const VERSION = 'V1.14.2.8.4.7.11'
const result = await runPlaywrightWithDevServer([
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/formalPaymentOrderDraftFilterCompleteness.spec.js',
])

if (result.stdout) process.stdout.write(result.stdout)
if (result.stderr) process.stderr.write(result.stderr)
if (result.error || result.status !== 0) {
  console.error(`${VERSION} formal payment order draft filter completeness gate failed.`)
  if (result.error) console.error(result.error.message)
  process.exit(result.status || 1)
}
console.log(`${VERSION} formal payment order draft filter completeness gate passed.`)
