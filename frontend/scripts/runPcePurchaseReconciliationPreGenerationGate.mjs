import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const checkpointRoot = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const previousId = 'supplier_settlement_pre_reconciliation_semantics_ready'
const targetId = 'purchase_reconciliation_pre_generation_design_ready'
const batchId = `prc-candidate-${Date.now()}-${process.pid}`
const stagingDir = path.join(checkpointRoot, '.staging', `${targetId}-${batchId}`)
const targetDir = path.join(checkpointRoot, targetId)
const reportPath = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'purchase-reconciliation-pre-generation-report.json')
const playwrightCli = path.join(root, 'node_modules', '@playwright', 'test', 'cli.js')
const previousDir = path.join(checkpointRoot, previousId)

const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
function run(args, env = {}) {
  const result = spawnSync(process.execPath, args, { cwd: root, env: { ...process.env, ...env }, stdio: 'inherit' })
  if ((result.status ?? 1) !== 0) process.exit(result.status ?? 1)
}
function integrityHash(directory) {
  const hash = crypto.createHash('sha256')
  for (const name of ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']) {
    hash.update(name); hash.update(fs.readFileSync(path.join(directory, name)))
  }
  return hash.digest('hex')
}

if (!fs.existsSync(previousDir)) throw new Error(`previous checkpoint missing: ${previousId}`)
const previousManifest = JSON.parse(fs.readFileSync(path.join(previousDir, 'manifest.json'), 'utf8'))
for (const [field, expected] of Object.entries({ version: 'V1.14.2.8.4.7.35', immutable: true, canaryGroup: true, singleCanary: false, zeroReconciliationObjectBoundary: true, zeroPaymentObjectBoundary: true, navigationOnly: true })) {
  if (previousManifest[field] !== expected) throw new Error(`previous checkpoint contract mismatch: ${field}`)
}
if (fs.existsSync(targetDir)) throw new Error(`formal checkpoint already exists: ${targetDir}`)
fs.mkdirSync(stagingDir, { recursive: true })
const env = { PCE_CANARY_BATCH_ID: batchId, PCE_CANARY_STAGING_DIR: stagingDir, PCE_GOLDEN_RUNNER_TRACE: '1' }
run(['scripts/verifyPurchaseReconciliationPrecheckMatrix.mjs'], env)
run([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/purchaseReconciliationPreGenerationDesign.spec.js', '-g', '金丝雀群 A-J'], env)
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'))
if (report.result !== 'passed' || report.canaryBatchId !== batchId || report.canaryScenarioCount !== 10) throw new Error('pre-generation report identity or result mismatch')
if (!report.protectedCheckpointHashesUnchanged || report.businessDataModified !== false || report.networkWriteRequestCount !== 0 || report.localStorageWriteCount !== 0) throw new Error('zero-write or protected checkpoint boundary failed')
const tracePath = path.resolve(report.runnerTraceExpectedPath)
if (path.dirname(tracePath) !== path.resolve(report.playwrightOutputDir) || !fs.existsSync(tracePath)) throw new Error('runner trace ownership mismatch')
fs.copyFileSync(tracePath, path.join(stagingDir, 'trace.zip'))
run([playwrightCli, 'test', '-c', 'playwright.runtime.config.js', 'tests/e2e/purchaseReconciliationPreGenerationDesign.spec.js', '-g', '跨进程稳定性恢复'], { ...env, PCE_CANARY_RECOVERY: '1' })
report.crossProcessRecovery = 'passed'
report.runnerTracePath = tracePath
report.checkpoint = targetDir
writeJson(reportPath, report)
const storage = JSON.parse(fs.readFileSync(path.join(stagingDir, 'storage-state.json'), 'utf8'))
const origin = process.env.PCE_BASE_URL || 'http://localhost:5173'
const localEntries = storage.origins?.find((item) => item.origin === origin)?.localStorage || []
writeJson(path.join(stagingDir, 'application-state.json'), { version: 'V1.14.2.8.4.7.36', origin, canaryBatchId: batchId, canaryGroup: true, localStorage: Object.fromEntries(localEntries.map((item) => [item.name, item.value])), capturedAt: new Date().toISOString() })
writeJson(path.join(stagingDir, 'business-entities.json'), {
  version: 'V1.14.2.8.4.7.36', origin: 'canary', canaryBatchId: batchId, canaryGroup: true, singleCanary: false,
  domainModelReady: true, sourceMappingReady: true, uniquenessPolicyReady: true, purePrecheckReady: true,
  runtimeCreationAllowed: false, formalNumberAllocated: false, zeroPurchaseReconciliationWrite: true, zeroPaymentObjectWrite: true,
  scenarios: report.scenarioResults,
})
writeJson(path.join(stagingDir, 'relationship-graph.json'), {
  version: 'V1.14.2.8.4.7.36', canaryBatchId: batchId,
  directSourceRelation: 'supplierSettlement -> purchaseReconciliationCandidate', upstreamEvidenceChain: ['priceApproval', 'purchaseOrder', 'receipt', 'inspection', 'warehouseTaskOrInventoryTransaction', 'payablePrepare', 'payableCheck', 'supplierSettlement'],
  uniquenessPolicy: report.uniquenessPolicy, mappingMatrix: report.mappingMatrix,
  purchaseReconciliationObjectCount: 0, paymentObjectCount: 0,
})
writeJson(path.join(stagingDir, 'restore-verification.json'), { checkpointId: targetId, status: 'passed', result: 'passed', verificationProcess: 'independent_node_playwright_process', verifiedAt: new Date().toISOString(), canaryBatchId: batchId, businessDataModified: false })
const hash = integrityHash(stagingDir)
writeJson(path.join(stagingDir, 'manifest.json'), {
  checkpointVersion: '1.0.0', version: 'V1.14.2.8.4.7.36', checkpointId: targetId, createdAt: new Date().toISOString(), origin,
  sourceCheckpointId: previousId, nextStageId: 'purchase-reconciliation-object-generation-review',
  entityIds: report.scenarioResults.map((item) => item.candidateId).filter(Boolean),
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'], integrityHash: hash,
  restorable: true, immutable: true, canaryGroup: true, singleCanary: false,
  domainModelReady: true, sourceMappingReady: true, uniquenessPolicyReady: true, purePrecheckReady: true,
  runtimeCreationAllowed: false, formalNumberAllocated: false, zeroPurchaseReconciliationWrite: true, zeroPaymentObjectWrite: true,
  canaryBatchId: batchId, userProfileOpened: false, userBusinessDataModified: false,
})
for (const name of ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json', 'restore-verification.json', 'checkpoint-screenshot.png', 'trace.zip']) if (!fs.existsSync(path.join(stagingDir, name))) throw new Error(`checkpoint file missing: ${name}`)
fs.renameSync(stagingDir, targetDir)
console.log(JSON.stringify({ version: 'V1.14.2.8.4.7.36', checkpointPath: targetDir, canaryBatchId: batchId, canaryScenarioCount: 10, pureFunctionCaseCount: report.pureFunctionCaseCount, matrixCaseCount: report.matrixCaseCount, crossProcessRecovery: 'passed', protectedCheckpointHashesUnchanged: true, formalNumberAllocationCount: 0, purchaseReconciliationWriteCount: 0, paymentObjectWriteCount: 0, traceHash: sha256(path.join(targetDir, 'trace.zip')), businessDataModified: false, result: 'passed' }, null, 2))
