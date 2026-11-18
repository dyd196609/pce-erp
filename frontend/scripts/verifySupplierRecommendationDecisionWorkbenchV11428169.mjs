import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const current = run(['--test', 'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const regression = run(['scripts/verifySupplierRecommendationActionExecutabilityV11428168.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const pass = current.status === 0
const model = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const gatePage = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const process011 = fs.readFileSync(path.join(governanceRoot, '流程节点真实运行验收规范.md'), 'utf8')
const caseLibrary = fs.readFileSync(path.join(governanceRoot, '问题案例库.md'), 'utf8')
const checks = [
  ['Decision Batch', pass && ['batchId', 'sourcePriceApprovalBatch', 'sourceQuoteComparisonBatch', 'items']
    .every(field => model.includes(field)) && model.includes('SupplierRecommendationDecisionBatchResult')],
  ['Multi Material', pass && model.includes('createSupplierRecommendationDecisionItemV11428169')
    && page.includes('material-recommendation-list')],
  ['Supplier Comparison', pass && page.includes('supplier-comparison')
    && page.includes('supplierCandidates.map')],
  ['Manual Decision', pass && model.includes('executeSelectDecisionBatchSupplierV11428169')
    && page.includes('SELECT_DECISION_BATCH_SUPPLIER')],
  ['Batch Confirm', pass && model.includes('executeConfirmSupplierRecommendationDecisionBatchV11428169')
    && page.includes('CONFIRM_RECOMMENDATION_DECISION_BATCH')],
  ['Gate Handoff', pass && model.includes('SupplierRecommendationDecisionBatchGateHandoff')
    && model.includes('purchaseOrderCreated: false') && gatePage.includes('decision-batch-gate-handoff')],
  ['PROCESS-011', pass && ['Object Exists PASS', 'Page Exists PASS', 'Data Handoff PASS',
    'Human Action Loop PASS', 'Entry Consistency PASS', 'Action Executability PASS']
    .every(value => process011.includes(value)) && pricePage.includes('supplierRecommendationRouteContextResolverV11428171')
    && processRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428171')
    && caseLibrary.includes('CASE-SCM-048')],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.9')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_DECISION_WORKBENCH_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_DECISION_WORKBENCH_ISSUES_FOUND')
if (!passed) process.exitCode = 1
