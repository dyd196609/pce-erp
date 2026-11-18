import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { runPlaywrightWithDevServer } from './pcePlaywrightRunner.mjs'

const VERSION = 'V1.14.2.8.4.4'
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const isWindows = process.platform === 'win32'
const npmCommand = isWindows ? 'npm.cmd' : 'npm'

function runStep(name, command, args) {
  console.log(`Running: ${name}`)
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: 'utf8',
    maxBuffer: 200 * 1024 * 1024,
    shell: isWindows,
  })
  if (result.stdout) process.stdout.write(result.stdout)
  if (result.stderr) process.stderr.write(result.stderr)
  if (result.error) {
    console.error(`${VERSION} ${name} failed: ${result.error.message}`)
    return false
  }
  return result.status === 0
}

async function runPlaywrightStep(name, args) {
  console.log(`Running: ${name}`)
  const result = await runPlaywrightWithDevServer(args)
  if (result.stdout) process.stdout.write(result.stdout)
  if (result.stderr) process.stderr.write(result.stderr)
  if (result.error) {
    console.error(`${VERSION} ${name} failed: ${result.error.message}`)
    return false
  }
  return result.status === 0
}

const canonicalNamesPassed = runStep('verify-pce-canonical-names', npmCommand, ['run', 'verify:pce-canonical-names'])
const allBusinessOperationColumnsPassed = runStep('verify-all-business-operation-evidence', npmCommand, ['run', 'verify:pce-all-business-operation-evidence'])
const operationColumnLayoutPassed = runStep('verify-pce-operation-column-layout', npmCommand, ['run', 'verify:pce-operation-column-layout'])
const listRequiredControlsPassed = runStep('verify-pce-list-required-controls', npmCommand, ['run', 'verify:pce-list-required-controls'])
const fixedColumnsPassed = runStep('verify-pce-fixed-columns', npmCommand, ['run', 'verify:pce-fixed-columns'])
const horizontalScrollPassed = runStep('verify-pce-horizontal-scroll', npmCommand, ['run', 'verify:pce-horizontal-scroll'])
const enforcementPassed = runStep('verify-pce-page-enforcement', npmCommand, ['run', 'verify:pce-page-enforcement'])
const phaseAFinanceLayoutPassed = runStep('phase-a-finance-table-layout', npmCommand, ['run', 'verify:pce-finance-table-layout'])
const runtimePassed = await runPlaywrightStep('playwright-real-table-runtime', [
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/ui-baseline/pceUiBaselineRuntime.spec.js',
  'tests/ui-baseline/pceEveryRouteBaseline.spec.js',
])
const reportPassed = runStep('generate-real-evidence-completion-report', process.execPath, [
  'scripts/generatePceBaselineCompletionReport.mjs',
])

if (!canonicalNamesPassed || !allBusinessOperationColumnsPassed || !operationColumnLayoutPassed || !listRequiredControlsPassed || !fixedColumnsPassed || !horizontalScrollPassed || !enforcementPassed || !phaseAFinanceLayoutPassed || !runtimePassed || !reportPassed) {
  console.error(`${VERSION} PCE runtime verification failed; completion report was generated from available evidence.`)
  process.exit(1)
}

console.log(`${VERSION} PCE runtime verification passed.`)
process.exit(0)
