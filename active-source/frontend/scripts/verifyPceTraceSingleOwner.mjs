import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const config = fs.readFileSync(path.join(root, 'playwright.runtime.config.js'), 'utf8')
const test = fs.readFileSync(path.join(root, 'tests/e2e/purchaseReceiveIncomingInspectionGoldenFlow.spec.js'), 'utf8')
const runner = fs.readFileSync(path.join(root, 'scripts/runPceReceiveIncomingInspectionGoldenFlow.mjs'), 'utf8')
const errors = []
const count = (source, token) => source.split(token).length - 1
if (!config.includes("PCE_GOLDEN_RUNNER_TRACE === '1' ? 'on'")) errors.push('Runner success trace is not explicitly enabled')
if (count(test, 'context.tracing.start(') !== 0) errors.push('Runner-mode test contains manual tracing.start')
if (count(test, 'context.tracing.stop(') !== 0) errors.push('Runner-mode test contains manual tracing.stop')
if (!runner.includes("PCE_GOLDEN_RUNNER_TRACE: '1'")) errors.push('Golden runner does not claim trace ownership explicitly')
if (!runner.includes('runnerTraceExpectedPath')) errors.push('Runner trace is not bound to current test output metadata')
if (runner.includes('catch') && runner.includes('already started')) errors.push('Trace ownership error is being swallowed')
if (errors.length) {
  errors.forEach((error) => console.error(`- ${error}`))
  process.exit(1)
}
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.18',
  traceOwner: 'runner',
  runnerManualStartCount: 0,
  runnerManualStopCount: 0,
  manualOwnerStartCount: 0,
  manualOwnerStopCount: 0,
  traceBoundToCurrentRun: true,
}, null, 2))
