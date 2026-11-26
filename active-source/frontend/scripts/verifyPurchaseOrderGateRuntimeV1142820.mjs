import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820 } from '../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '页面Route与业务Context分离规范.md', '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('PCE-ERP开发治理总规范.md').includes('BATCH-COMPLETENESS-001')
  && readGovernance('流程节点真实运行验收规范.md').includes('Batch Completeness')
  && readGovernance('一页一验收规范.md').includes('Batch Decision Completeness Check')

const makeItem = (index, confirmed = true) => ({
  decisionItemId: `SRDI-VERIFY-${index}`, materialCode: `MAT-VERIFY-${index}`,
  materialName: `验收物料${index}`,
  selectedSupplierCode: confirmed ? `SUP-${index}` : '',
  selectedSupplierName: confirmed ? `供应商${index}` : '',
  selectionReason: confirmed ? '人工复核报价、历史价格和资格证据后确认。' : '',
  reviewStatus: confirmed ? 'confirmed' : 'manual_review',
  reviewer: confirmed ? '验收采购员20' : '',
  reviewedAt: confirmed ? '2026-08-06T20:00:00.000Z' : '',
  status: confirmed ? 'confirmed' : 'selected',
  supplierCandidates: [{ supplierCode: `SUP-${index}`, supplierName: `供应商${index}`,
    quotePrice: 100 + index }],
  priceEvidence: [{ supplierCode: `SUP-${index}`, currentPrice: 100 + index,
    evidenceSource: 'QuoteComparison' }, { supplierCode: `SUP-${index}`,
    historyPrice: 95 + index, evidenceSource: 'PurchaseOrderHistory' }],
  quoteComparisonIds: [`QC-VERIFY-${index}`],
})
const makeSource = index => ({ materialCode: `MAT-VERIFY-${index}`,
  quoteComparisonIds: [`QC-VERIFY-${index}`],
  supplierCandidates: [{ supplierCode: `SUP-${index}`, supplierName: `供应商${index}`,
    quotePrice: 100 + index }],
  priceEvidence: [{ supplierCode: `SUP-${index}`, currentPrice: 100 + index,
    evidenceSource: 'QuoteComparison' }, { supplierCode: `SUP-${index}`,
    historyPrice: 95 + index, evidenceSource: 'PurchaseOrderHistory' }],
  priceReferenceContexts: [{ supplierCode: `SUP-${index}`, historyPrice: 95 + index,
    evidenceSource: 'PriceReferenceContext' }],
})
const input = (count, incomplete = 0) => ({
  decisionBatchResult: { objectType: 'SupplierRecommendationDecisionBatchResult',
    batchId: `SRDB-VERIFY-${count}-${incomplete}`, status: 'confirmed',
    items: Array.from({ length: count }, (_, index) => makeItem(index + 1, incomplete !== index + 1)),
    purchaseOrderCreated: false },
  purchaseContext: { sourceRequestNos: ['PR-VERIFY-20'], sourceInquiryNos: ['PI-VERIFY-20'] },
  sourceItems: Array.from({ length: count }, (_, index) => makeSource(index + 1)),
})
const evaluate = value => evaluatePurchaseOrderCreationGateDecisionV1142820(
  createPurchaseOrderCreationGateDecisionV1142820(value))
const canaryA = evaluate(input(1))
const canaryB = evaluate(input(13))
const canaryC = evaluate(input(13, 7))

const current = run(['--test', 'tests/acceptance/purchaseOrderGateRuntimeV1142820.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/enterprisePurchaseOrderCreationGateRuntimeV1142814.test.mjs',
  'tests/acceptance/supplierRecommendationHumanDecisionV1142819.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const page = read('src/meta/pages/ScmPurchaseOrderGatePage.vue')
const model = read('src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js')
const provider = read('src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js')
const cases = readGovernance('问题案例库.md')
const decisionBatchInput = current.status === 0
  && [canaryA, canaryB, canaryC].every(value => value.sourceObjectType
    === 'SupplierRecommendationDecisionBatchResult')
  && provider.includes('SupplierRecommendationDecisionBatchResult')
const batchCompleteness = canaryA.batchCompleteness.completedItemCount === 1
  && canaryB.batchCompleteness.completedItemCount === 13
  && canaryC.batchCompleteness.pendingItemCount === 1
const decisionConfirm = canaryB.items.every(item => item.reviewStatus === 'confirmed')
const supplierCompleteness = canaryB.items.every(item => item.selectedSupplierCode
  && item.selectedSupplierName)
const gateRule = canaryB.checks.length === 6 && ['BATCH_COMPLETENESS', 'DECISION_STATUS',
  'SUPPLIER_COMPLETENESS', 'MANUAL_CONFIRMATION', 'BUSINESS_EVIDENCE',
  'HISTORICAL_PO_ISOLATION']
  .every(code => canaryB.checks.some(check => check.checkCode === code))
const readyState = canaryA.status === 'ready_for_purchase_order'
  && canaryB.status === 'ready_for_purchase_order'
const blockedState = canaryC.status === 'blocked'
  && canaryC.blockedReasons.includes('当前推荐批次仍有未完成物料决策')
const noPurchaseOrder = [canaryA, canaryB, canaryC].every(value => !value.purchaseOrderCreated
  && !value.purchaseOrderSubmitted && !value.purchaseOrderApproved)
  && !page.includes('data-process-action="CREATE_PURCHASE_ORDER"')
  && model.includes('supplierAutoSelected: false') && model.includes('recommendationModified: false')
const process011 = current.status === 0 && routeRegression.status === 0
  && ['gate-purchase-context', 'decision-batch-gate-handoff', 'batch-completeness',
    'gate-check-results', 'gate-human-audit', 'EVALUATE_PURCHASE_ORDER_CREATION_GATE']
    .every(value => page.includes(value))
  && provider.includes('supplierRecommendationDataHandoffProviderV1142818')
  && cases.includes('CASE-SCM-057')

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['DecisionBatch Input', decisionBatchInput],
  ['Batch Completeness', batchCompleteness],
  ['Decision Confirm', decisionConfirm],
  ['Supplier Completeness', supplierCompleteness],
  ['Gate Rule', gateRule],
  ['Ready State', readyState],
  ['Blocked State', blockedState],
  ['No PurchaseOrder', noPurchaseOrder],
  ['PROCESS-011', process011],
  ['Regression', regression.status === 0 && routeRegression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.20')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
for (const layer of ['Object Exists', 'Page Exists', 'Data Handoff', 'Human Action Loop',
  'Entry Consistency', 'Action Executability', 'Route Identity', 'Context Separation']) {
  console.log(`${layer} ${process011 ? 'PASS' : 'FAIL'}`)
}
console.log(`Batch Completeness ${batchCompleteness ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_PURCHASE_ORDER_GATE_RUNTIME_READY'
  : 'SCM_PURCHASE_ORDER_GATE_RUNTIME_ISSUES_FOUND')
if (!passed) process.exitCode = 1
