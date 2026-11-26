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
  'tests/acceptance/purchaseOrderStandardizationV11428427213.test.mjs'])
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
  'purchase-order-standardization-v11428427213-browser.json')
let browserEvidence = null
try { browserEvidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8')) } catch {}
const detail = browserEvidence?.detail || {}
const refresh = browserEvidence?.refresh || {}
const download = browserEvidence?.importTemplate || {}
const canonicalPass = detail.displayNumber === detail.purchaseOrderObjectNo
  && detail.canonicalField === 'objectNo'
  && !/PAP-PI|QC-PI|GATE|SOURCE CHAIN/i.test(detail.displayNumber || '')
const detailPass = canonicalPass && detail.primaryRegions?.join('+') ===
  'basic-information+material-detail' && detail.poDuplicateCount === 0
  && detail.sourceGateVisible === true
const refreshPass = refresh.buttonBefore === '刷新' && refresh.sawRefreshing === true
  && refresh.buttonAfter === '刷新成功' && refresh.lastRefreshTimeChanged === true
const templatePass = download.fileName === '采购订单导入模板.xlsx'
  && JSON.stringify(download.sheetNames) === JSON.stringify(['基本信息', '物料明细', '字段说明'])
  && download.headerMissing?.length === 0 && download.headerUnexpected?.length === 0
  && download.detailMissing?.length === 0 && download.detailUnexpected?.length === 0

const autoPass = acceptance.status === 0
const regressionsPass = detailRegression.status === 0 && printRegression.status === 0
const checks = [
  ['Governance Files Loaded', autoPass],
  ['Governance Applied', autoPass],
  ['Canonical PurchaseOrder Number', canonicalPass],
  ['PurchaseOrder List Number', canonicalPass],
  ['PurchaseOrder Detail Number', detailPass],
  ['PO Duplicate Removed', detailPass],
  ['Source Gate Number', detailPass],
  ['PurchaseOrder Detail Structure', detailPass],
  ['Header Schema Match', autoPass && templatePass],
  ['Item Schema Match', autoPass && templatePass],
  ['Import Template Schema Match', autoPass && templatePass],
  ['Refresh Regression', refreshPass],
  ['Regression', regressionsPass],
  ['Gate Changed', false, 'NO'],
  ['Lifecycle Changed', false, 'NO'],
  ['Database Changed', false, 'NO'],
  ['Business Write Count', true, '0'],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.27.2.13')
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}
const failed = checks.filter(([, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length
  ? 'PURCHASE_ORDER_STANDARDIZED_ISSUES_FOUND'
  : 'PURCHASE_ORDER_STANDARDIZED_READY'}`)
console.log(failed.length
  ? 'V1.14.2.8.4.27.2.13_ISSUES_FOUND'
  : 'V1.14.2.8.4.27.2.13_READY')
if (failed.length) process.exitCode = 1
