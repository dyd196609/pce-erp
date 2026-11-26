import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { finalizeStagedCheckpoint, verifyCheckpointIntegrity } from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const verifyExisting = process.argv.includes('--verify-existing')
const runId = `payable-prepared-${Date.now()}-${process.pid}`
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'payable-prepare-golden-flow-report.json')

function run(args, extraEnv = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, PCE_GOLDEN_RUNNER_TRACE: '1', ...extraEnv }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex')
}

run(['scripts/verifyPcePayablePrepareGoldenFlow.mjs'])

if (verifyExisting) {
  const checkpoint = await verifyCheckpointIntegrity('payable_prepared', { expectedOrigin: process.env.PCE_BASE_URL || 'http://localhost:5173' })
  run(['scripts/runPceGoldenCheckpointRestore.mjs', 'payable_prepared'])
  const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
  if (report.overall !== 'passed' || report.directStoreCallCount !== 0 || report.userBusinessDataModified !== false) throw new Error('existing payable prepare golden report is invalid')
  console.log(JSON.stringify({
    version: 'V1.14.2.8.4.7.32',
    mode: 'verify_existing',
    checkpointPath: checkpoint.directory,
    payablePrepareNo: report.payablePrepareNo,
    directStoreCallCount: report.directStoreCallCount,
    userBusinessDataModified: report.userBusinessDataModified,
    overall: 'passed',
  }, null, 2))
  process.exit(0)
}

run([path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'), 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/payablePrepareGoldenFlow.spec.js'], {
  PCE_GOLDEN_RUNNER_TRACE: '1',
  PCE_GOLDEN_RUN_ID: runId,
})
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
if (report.runId !== runId || report.overall !== 'passed') throw new Error('runner report identity or result mismatch')
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir)) throw new Error('runner trace output mismatch')
if (!fs.statSync(tracePath).isFile() || fs.statSync(tracePath).size <= 0) throw new Error('runner trace missing')
const traceDirectory = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'runner-traces', runId)
fs.mkdirSync(traceDirectory, { recursive: true })
const stableTracePath = path.join(traceDirectory, 'trace.zip')
fs.copyFileSync(tracePath, stableTracePath)
run(['scripts/verifyPceStagedPayablePreparedCheckpoint.mjs', report.targetCheckpointPath], { PCE_GOLDEN_RUN_ID: runId })
const checkpoint = await finalizeStagedCheckpoint({ checkpointId: 'payable_prepared', runId, tracePath: stableTracePath })
const checkpointTracePath = path.join(checkpoint.directory, 'trace.zip')
const runnerTraceHash = sha256(stableTracePath)
const checkpointTraceHash = sha256(checkpointTracePath)
if (runnerTraceHash !== checkpointTraceHash) throw new Error('runner trace and checkpoint trace hash mismatch')
run(['scripts/runPceGoldenCheckpointRestore.mjs', 'payable_prepared'])
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.32',
  runId,
  checkpointPath: checkpoint.directory,
  runnerTracePath: stableTracePath,
  runnerTraceHash,
  checkpointTraceHash,
  traceHashesMatched: true,
  payablePrepareNo: report.payablePrepareNo,
  payableCheckGenerated: false,
  supplierSettlementGenerated: false,
  directStoreCallCount: 0,
  userBusinessDataModified: false,
  overall: 'passed',
}, null, 2))
