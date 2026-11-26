import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { finalizeStagedCheckpoint } from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const runId = `qualified-inbound-completed-${Date.now()}-${process.pid}`
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'qualified-inbound-completion-report.json')
function run(args, extraEnv = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, PCE_GOLDEN_RUNNER_TRACE: '1', ...extraEnv }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

run(['scripts/verifyPceTraceSingleOwner.mjs'])
run(['scripts/verifyPceQualifiedInboundCompletionGoldenFlow.mjs'])
run([path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'), 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/qualifiedInboundCompletionGoldenFlow.spec.js'], {
  PCE_GOLDEN_RUNNER_TRACE: '1',
  PCE_GOLDEN_RUN_ID: runId,
})
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
if (report.runId !== runId) throw new Error('runner report runId mismatch')
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir)) throw new Error('runner trace output mismatch')
if (!fs.statSync(tracePath).isFile() || fs.statSync(tracePath).size <= 0) throw new Error('runner trace missing')
const traceDirectory = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'runner-traces', runId)
fs.mkdirSync(traceDirectory, { recursive: true })
const stableTracePath = path.join(traceDirectory, 'trace.zip')
fs.copyFileSync(tracePath, stableTracePath)
run(['scripts/verifyPceStagedQualifiedInboundCompletedCheckpoint.mjs', report.targetCheckpointPath], { PCE_GOLDEN_RUN_ID: runId })
await finalizeStagedCheckpoint({ checkpointId: 'qualified_inbound_completed', runId, tracePath: stableTracePath })
run(['scripts/runPceGoldenCheckpointRestore.mjs', 'qualified_inbound_completed'])
