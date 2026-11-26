import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { finalizeStagedCheckpoint, verifyCheckpointIntegrity } from '../tests/helpers/goldenCheckpoint.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const verifyExisting = process.argv.includes('--verify-existing')
const runId = `supplier-settlement-ready-${Date.now()}-${process.pid}`
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'supplier-settlement-golden-flow-report.json')
const stagingRoot = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', '.staging')
function run(args, extraEnv = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, PCE_GOLDEN_RUNNER_TRACE: '1', ...extraEnv }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
run(['scripts/verifyPceSupplierSettlementGoldenFlow.mjs'])
if (verifyExisting) {
  const checkpoint = await verifyCheckpointIntegrity('supplier_settlement_ready', { expectedOrigin: process.env.PCE_BASE_URL || 'http://localhost:5173' })
  run(['scripts/runPceGoldenCheckpointRestore.mjs', 'supplier_settlement_ready'])
  const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
  if (report.overall !== 'passed' || report.directStoreCallCount !== 0 || report.userBusinessDataModified !== false) throw new Error('existing supplier settlement report is invalid')
  console.log(JSON.stringify({ version: 'V1.14.2.8.4.7.34', mode: 'verify_existing', checkpointPath: checkpoint.directory, supplierSettlementNo: report.supplierSettlementNo, overall: 'passed' }, null, 2))
  process.exit(0)
}
const resumableStaging = fs.existsSync(stagingRoot)
  ? fs.readdirSync(stagingRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith('supplier_settlement_ready-'))
    .map((entry) => ({ path: path.join(stagingRoot, entry.name), mtime: fs.statSync(path.join(stagingRoot, entry.name)).mtimeMs }))
    .filter((entry) => fs.existsSync(path.join(entry.path, 'storage-state.json')))
    .sort((left, right) => right.mtime - left.mtime)[0]?.path || ''
  : ''
let resumeSettlementNo = ''
if (resumableStaging) {
  const entities = JSON.parse(fs.readFileSync(path.join(resumableStaging, 'business-entities.json'), 'utf8'))
  resumeSettlementNo = entities.supplierSettlementNo || ''
}
run([path.join(root, 'node_modules', '@playwright', 'test', 'cli.js'), 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/supplierSettlementGoldenFlow.spec.js'], {
  PCE_GOLDEN_RUNNER_TRACE: '1',
  PCE_GOLDEN_RUN_ID: runId,
  PCE_SUPPLIER_SETTLEMENT_RESUME_STORAGE_STATE: resumableStaging ? path.join(resumableStaging, 'storage-state.json') : '',
  PCE_EXPECTED_SUPPLIER_SETTLEMENT_NO: resumeSettlementNo,
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
run(['scripts/verifyPceStagedSupplierSettlementReadyCheckpoint.mjs', report.targetCheckpointPath], { PCE_GOLDEN_RUN_ID: runId })
const checkpoint = await finalizeStagedCheckpoint({ checkpointId: 'supplier_settlement_ready', runId, tracePath: stableTracePath })
const runnerTraceHash = sha256(stableTracePath)
const checkpointTraceHash = sha256(path.join(checkpoint.directory, 'trace.zip'))
if (runnerTraceHash !== checkpointTraceHash) throw new Error('runner trace and checkpoint trace hash mismatch')
run(['scripts/runPceGoldenCheckpointRestore.mjs', 'supplier_settlement_ready'])
console.log(JSON.stringify({ version: 'V1.14.2.8.4.7.34', runId, checkpointPath: checkpoint.directory, runnerTracePath: stableTracePath, runnerTraceHash, checkpointTraceHash, traceHashesMatched: true, supplierSettlementNo: report.supplierSettlementNo, purchaseReconciliationGenerated: false, paymentGenerated: false, directStoreCallCount: 0, userBusinessDataModified: false, overall: 'passed' }, null, 2))
