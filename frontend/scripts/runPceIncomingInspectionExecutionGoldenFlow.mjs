import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { finalizeStagedCheckpoint } from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const runId = `incoming-inspection-passed-${Date.now()}-${process.pid}`
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'incoming-inspection-execution-report.json')

function run(args, extraEnv = {}) {
  const result = spawnSync(process.execPath, args, {
    cwd: root,
    env: { ...process.env, PCE_GOLDEN_RUNNER_TRACE: '1', ...extraEnv },
    stdio: 'inherit',
  })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

run(['scripts/verifyPceTraceSingleOwner.mjs'])
run(['scripts/verifyPceIncomingInspectionExecutionGoldenFlow.mjs'])
run([
  path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'),
  'test',
  '-c',
  'playwright.runtime.config.js',
  'tests/e2e/incomingInspectionExecutionGoldenFlow.spec.js',
], { PCE_GOLDEN_RUNNER_TRACE: '1', PCE_GOLDEN_RUN_ID: runId })

const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
if (report.runId !== runId) throw new Error(`runner trace runId mismatch: ${report.runId} !== ${runId}`)
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir)) throw new Error('runner trace output directory mismatch')
const traceStat = fs.statSync(tracePath)
if (!traceStat.isFile() || traceStat.size <= 0) throw new Error('current runner trace is missing or empty')
const stableTraceDirectory = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'runner-traces', runId)
fs.mkdirSync(stableTraceDirectory, { recursive: true })
const stableTracePath = path.join(stableTraceDirectory, 'trace.zip')
fs.copyFileSync(tracePath, stableTracePath)
run(['scripts/verifyPceStagedIncomingInspectionPassedCheckpoint.mjs', report.targetCheckpointPath], { PCE_GOLDEN_RUN_ID: runId })
await finalizeStagedCheckpoint({ checkpointId: 'incoming_inspection_passed', runId, tracePath: stableTracePath })
run(['scripts/runPceGoldenCheckpointRestore.mjs', 'incoming_inspection_passed'])
