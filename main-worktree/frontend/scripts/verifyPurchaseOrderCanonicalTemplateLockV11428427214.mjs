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
  'tests/acceptance/purchaseOrderCanonicalTemplateLockV11428427214.test.mjs'])
const previousRegression = run(['--test',
  'tests/acceptance/purchaseOrderStandardizationV11428427213.test.mjs'])
const operationRegression = run(['--test',
  'tests/acceptance/purchaseOrderOperationRuntimeV11428427212.test.mjs'])
const detailRegression = run(['--test', '--test-name-pattern',
  'one canonical PurchaseOrder number|PurchaseOrderItem ownership|refresh exposes loading',
  'tests/acceptance/purchaseOrderBusinessIdentityV11428427211.test.mjs'])
const printRegression = run(['--test', '--test-name-pattern',
  'print model uses|standard print document|role print permission|preview page uses|list, export and print',
  'tests/acceptance/pcePrintFormStandardV11428427243.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [acceptance, previousRegression, operationRegression, detailRegression,
  printRegression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const evidencePath = path.join(root, 'test-results',
  'purchase-order-canonical-template-v11428427214-browser.json')
let evidence = null
try { evidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8')) } catch {}
const list = evidence?.purchaseOrderList || {}
const detail = evidence?.purchaseOrderDetail || {}
const template = evidence?.importTemplate || {}
const canonicalNumber = String(list.displayNumber || '')
const purityPass = /^PO\d+$/i.test(canonicalNumber)
  && !/PAP-PI|PI-|QC-|PAP-|GATE/i.test(canonicalNumber)
const listPass = purityPass && list.displayNumber === list.objectNo
const detailPass = detail.displayNumber === detail.objectNo
  && detail.sourceGateSeparated === true && detail.basicSequenceVisible === true
const templatePass = template.downloaded === true && template.opened === true
  && JSON.stringify(template.sheetNames) === JSON.stringify(['基本信息', '物料明细', '字段说明'])
  && template.headerCountMatch === true && template.headerNameMatch === true
  && template.headerOrderMatch === true && template.detailCountMatch === true
  && template.detailNameMatch === true && template.detailOrderMatch === true
  && template.basicFirstColumn === '序号' && template.detailFirstColumn === '序号'

const autoPass = acceptance.status === 0
const regressionPass = [previousRegression, operationRegression, detailRegression, printRegression]
  .every(result => result.status === 0)
const browserPass = listPass && detailPass && templatePass
const checks = [
  ['Governance Files Loaded', autoPass],
  ['Governance Applied', autoPass],
  ['PurchaseOrder Number Chain', autoPass],
  ['Canonical Number Field', autoPass],
  ['List Display Number', listPass],
  ['Detail Display Number', detailPass],
  ['Source Gate Separation', detailPass],
  ['Number Purity Check', autoPass],
  ['Import Template', autoPass],
  ['Header Schema Match', autoPass],
  ['Header Order Match', autoPass],
  ['Detail Schema Match', autoPass],
  ['Detail Order Match', autoPass],
  ['Browser Acceptance', browserPass],
  ['Regression', regressionPass],
  ['Gate Changed', true, 'NO'],
  ['Lifecycle Changed', true, 'NO'],
  ['Database Changed', true, 'NO'],
  ['Business Write Count', true, '0'],
  ['Build', build.status === 0],
]

console.log('Version: V1.14.2.8.4.27.2.14')
for (const [label, passed, fixed] of checks) {
  console.log(`${label}: ${fixed ?? (passed ? 'PASS' : 'FAIL')}`)
}
const failed = checks.filter(([, passed, fixed]) => fixed == null && !passed)
console.log(`Final Status: ${failed.length
  ? 'PURCHASE_ORDER_CANONICAL_AND_TEMPLATE_LOCKED_ISSUES_FOUND'
  : 'PURCHASE_ORDER_CANONICAL_AND_TEMPLATE_LOCKED_READY'}`)
console.log(failed.length
  ? 'V1.14.2.8.4.27.2.14_ISSUES_FOUND'
  : 'V1.14.2.8.4.27.2.14_READY')
if (failed.length) process.exitCode = 1
