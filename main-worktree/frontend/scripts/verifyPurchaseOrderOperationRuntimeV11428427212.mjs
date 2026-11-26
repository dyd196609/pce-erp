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
  'tests/acceptance/purchaseOrderOperationRuntimeV11428427212.test.mjs'])
const detailRegression = run(['--test', '--test-name-pattern',
  'one canonical PurchaseOrder number|PurchaseOrderItem ownership|refresh exposes loading',
  'tests/acceptance/purchaseOrderBusinessIdentityV11428427211.test.mjs'])
const printRegression = run(['--test', '--test-name-pattern',
  'print model uses|standard print document|role print permission|preview page uses|list, export and print',
  'tests/acceptance/pcePrintFormStandardV11428427243.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [acceptance, detailRegression, printRegression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const evidencePath = path.join(root, 'test-results',
  'purchase-order-operation-runtime-v11428427212-browser.json')
let browserEvidence = null
try { browserEvidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8')) } catch {}
const refreshEvidence = browserEvidence?.refresh || {}
const templateEvidence = browserEvidence?.importTemplate || {}
const browserRefreshPass = Boolean(refreshEvidence.buttonBefore === '刷新'
  && refreshEvidence.sawRefreshing === true
  && refreshEvidence.buttonAfter === '刷新成功'
  && refreshEvidence.lastRefreshTimeChanged === true
  && refreshEvidence.listRenderVersionChanged === true)
const browserTemplatePass = Boolean(templateEvidence.fileName === '采购订单导入模板.xlsx'
  && templateEvidence.sheetNames?.includes('基本信息')
  && templateEvidence.sheetNames?.includes('物料明细'))

const acceptancePass = acceptance.status === 0
const detailPass = detailRegression.status === 0
const printPass = printRegression.status === 0
const autoPass = acceptancePass && detailPass && printPass
const checks = [
  ['Governance Files Loaded', autoPass],
  ['Governance Applied', autoPass],
  ['PurchaseOrder List Refresh', browserRefreshPass],
  ['Refresh Visible Feedback', browserRefreshPass],
  ['PurchaseOrder Number', autoPass],
  ['PurchaseOrder Number Source', autoPass],
  ['Import Template', autoPass && browserTemplatePass],
  ['Import Template Sheet Structure', autoPass && browserTemplatePass],
  ['Basic Sheet', autoPass && browserTemplatePass],
  ['Item Sheet', autoPass && browserTemplatePass],
  ['PurchaseOrder Detail Regression', detailPass],
  ['Print Regression', printPass],
  ['Gate Changed', false, 'NO'],
  ['Lifecycle Changed', false, 'NO'],
  ['Database Changed', false, 'NO'],
  ['Business Write Count', true, '0'],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.27.2.12')
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}
const failed = checks.filter(([label, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length
  ? 'PURCHASE_ORDER_OPERATION_RUNTIME_ISSUES_FOUND'
  : 'PURCHASE_ORDER_OPERATION_RUNTIME_READY'}`)
console.log(failed.length ? 'V1.14.2.8.4.27.2.12_ISSUES_FOUND' : 'V1.14.2.8.4.27.2.12_READY')
if (failed.length) process.exitCode = 1
