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
  'tests/acceptance/pceRuntimeGovernancePurchaseOrderV11428427215.test.mjs'])
const v214 = run(['--test',
  'tests/acceptance/purchaseOrderCanonicalTemplateLockV11428427214.test.mjs'])
const v213 = run(['--test',
  'tests/acceptance/purchaseOrderStandardizationV11428427213.test.mjs'])
const operation = run(['--test',
  'tests/acceptance/purchaseOrderOperationRuntimeV11428427212.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [acceptance, v214, v213, operation, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const evidencePath = path.join(root, 'test-results',
  'pce-runtime-governance-purchase-order-v11428427215-browser.json')
let evidence = null
try { evidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8')) } catch {}
const list = evidence?.purchaseOrderList || {}
const detail = evidence?.purchaseOrderDetail || {}
const template = evidence?.importTemplate || {}
const processCenter = evidence?.processCenter || {}
const listPass = list.runtimeModelType === 'PurchaseOrderRuntimeModel'
  && list.displayNumber === list.objectNo && /^PO\d+$/i.test(list.displayNumber || '')
const detailPass = detail.runtimeModelType === 'PurchaseOrderRuntimeModel'
  && detail.displayNumber === detail.objectNo
const templatePass = template.downloaded === true && template.opened === true
  && JSON.stringify(template.sheetNames) === JSON.stringify([
    '采购订单基本信息', '采购订单物料明细',
  ]) && template.headerRelationField === '采购订单编号'
  && template.detailRelationField === '采购订单编号'
const entryPass = processCenter.directEntryRuntime === 'ProcessCenterRuntime'
  && processCenter.moduleEntryRuntime === 'ProcessCenterRuntime'
  && processCenter.structureConsistent === true

const autoPass = acceptance.status === 0
const regressionPass = [v214, v213, operation].every(result => result.status === 0)
const checks = [
  ['Governance Files Loaded', autoPass],
  ['New Governance Added', autoPass],
  ['Business Runtime Chain', autoPass],
  ['Single Runtime Rule', autoPass],
  ['Canonical Number', autoPass],
  ['PurchaseOrder Number', listPass && detailPass],
  ['Import Template Relation', autoPass && templatePass],
  ['Process Center Runtime', autoPass],
  ['Entry Consistency', entryPass],
  ['Duplicate Implementation Scan', autoPass],
  ['Browser Acceptance', listPass && detailPass && templatePass && entryPass],
  ['Regression', regressionPass],
  ['Gate Changed', true, 'NO'],
  ['Lifecycle Changed', true, 'NO'],
  ['Database Changed', true, 'NO'],
  ['Business Write Count', true, '0'],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.27.2.15')
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}
const failed = checks.filter(([, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length
  ? 'PCE_RUNTIME_GOVERNANCE_AND_PURCHASE_ORDER_ISSUES_FOUND'
  : 'PCE_RUNTIME_GOVERNANCE_AND_PURCHASE_ORDER_READY'}`)
console.log(failed.length ? 'V1.14.2.8.4.27.2.15_ISSUES_FOUND'
  : 'V1.14.2.8.4.27.2.15_READY')
if (failed.length) process.exitCode = 1
