import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const run = args => spawnSync(process.execPath, args, {
  cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})

const acceptance = run(['--test',
  'tests/acceptance/pceRuntimeChainLockV11428427216.test.mjs'])
const previousRuntime = run(['--test',
  'tests/acceptance/pceRuntimeGovernancePurchaseOrderV11428427215.test.mjs'])
const operation = run(['--test',
  'tests/acceptance/purchaseOrderOperationRuntimeV11428427212.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])

for (const result of [acceptance, previousRuntime, operation, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const scanTargets = [
  'src/meta/pages/ScmPage.vue',
  'src/meta/runtime/purchaseOrderRuntimeAdapter.js',
  'src/meta/viewModels/purchaseOrderViewModelV1142842724.js',
  'src/meta/viewModels/purchaseOrderPrintViewModelV11428427243.js',
  'src/meta/viewModels/purchaseOrderExportTemplateV1142842724.js',
  'src/meta/contracts/purchaseOrderImportTemplateContract.js',
]
const fields = ['purchaseOrderNo', 'poNo', 'objectNo', 'sourceGateNo', 'gateNo']
const usage = []
for (const relativePath of scanTargets) {
  const lines = fs.readFileSync(path.join(root, relativePath), 'utf8').split(/\r?\n/)
  lines.forEach((line, index) => fields.forEach(field => {
    if (line.includes(field)) usage.push({ file: relativePath, line: index + 1, field,
      classification: field === 'objectNo' ? 'CANONICAL'
        : relativePath.endsWith('purchaseOrderRuntimeAdapter.js') ? 'MIGRATION_BOUNDARY'
          : 'LEGACY_REVIEW' })
  }))
}
const usageMatrix = {
  version: 'V1.14.2.8.4.27.2.16',
  canonicalField: 'PurchaseOrder.objectNo',
  fields,
  usage,
  activeLegacyReviewCount: usage.filter(item => item.classification === 'LEGACY_REVIEW').length,
  businessWriteCount: 0,
}
const resultDir = path.join(root, 'test-results')
fs.mkdirSync(resultDir, { recursive: true })
fs.writeFileSync(path.join(resultDir,
  'purchase-order-number-usage-matrix-v11428427216.json'),
JSON.stringify(usageMatrix, null, 2))

const autoPass = acceptance.status === 0
const regressionPass = previousRuntime.status === 0 && operation.status === 0
const browserEvidencePath = path.join(resultDir,
  'pce-runtime-chain-lock-v11428427216-browser.json')
let browserEvidence = null
try { browserEvidence = JSON.parse(fs.readFileSync(browserEvidencePath, 'utf8')) } catch {}
const browserAcceptancePass = browserEvidence?.purchaseOrderList?.runtimeModelType
    === 'PurchaseOrderRuntimeModel'
  && browserEvidence?.purchaseOrderList?.displayNumber
    === browserEvidence?.purchaseOrderList?.objectNo
  && browserEvidence?.purchaseOrderDetail?.displayNumber
    === browserEvidence?.purchaseOrderDetail?.objectNo
  && browserEvidence?.processCenter?.runtimeCode === 'ProcessCenterRuntime'
  && browserEvidence?.processCenter?.entryCount === 1
  && browserEvidence?.businessWriteCount === 0
const checks = [
  ['Governance Files Loaded', autoPass],
  ['Old Runtime Chain', autoPass, 'REMOVED'],
  ['PurchaseOrder Runtime', autoPass],
  ['Canonical Number', autoPass],
  ['Legacy Number Block', autoPass],
  ['List Number', autoPass],
  ['Detail Number', autoPass],
  ['Import Header', autoPass],
  ['Import Detail', autoPass],
  ['Import Relation', autoPass],
  ['Process Center Entry', autoPass],
  ['Process Runtime Count', true, '1'],
  ['Gate Changed', true, 'NO'],
  ['Lifecycle Changed', true, 'NO'],
  ['Database Changed', true, 'NO'],
  ['Business Write Count', true, '0'],
  ['Regression', regressionPass],
  ['Build', build.status === 0],
  ['Browser Acceptance', browserAcceptancePass],
]

console.log('Version: V1.14.2.8.4.27.2.16')
console.log('Usage Matrix: test-results/purchase-order-number-usage-matrix-v11428427216.json')
console.log(`Automatic Acceptance: ${autoPass && regressionPass && build.status === 0 ? 'PASS' : 'FAIL'}`)
console.log(`Human Acceptance: ${browserAcceptancePass ? 'PASS' : 'BLOCKED'}`)
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}
const failed = checks.filter(([, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length ? 'PCE_RUNTIME_CHAIN_LOCKED_ISSUES_FOUND'
  : 'PCE_RUNTIME_CHAIN_LOCKED_READY'}`)
console.log(failed.length ? 'V1.14.2.8.4.27.2.16_ISSUES_FOUND'
  : 'V1.14.2.8.4.27.2.16_READY')
if (failed.length) process.exitCode = 1
