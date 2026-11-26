import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820,
} from '../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'
import { createPurchaseOrderCreationRequestsV1142821,
} from '../src/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderCreationRequestV1142821.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(root, '..')
const governanceRoot = path.join(repositoryRoot, 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '页面Route与业务Context分离规范.md', 'SCM采购订单准入Gate运行规范.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && readGovernance(name).trim()
}) && readGovernance('PCE-ERP开发治理总规范.md').includes('BATCH-COMPLETENESS-001')
  && readGovernance('CODEX执行命令规范.md').includes('CODEX-COMMAND-002')

const makeItem = (index, confirmed = true) => ({
  decisionItemId: `SRDI-VERIFY-21-${index}`, materialCode: `MAT-VERIFY-21-${index}`,
  materialName: `创建申请验收物料${index}`, quantity: index,
  sourcePriceApprovalIds: [`PA-VERIFY-21-${index}`],
  quoteComparisonIds: [`QC-VERIFY-21-${index}`],
  selectedSupplierCode: confirmed ? `SUP-VERIFY-21-${index % 2}` : '',
  selectedSupplierName: confirmed ? `创建申请供应商${index % 2}` : '',
  selectionReason: confirmed ? '采购员人工核验供应商报价、历史价格和资格证据后确认。' : '',
  reviewStatus: confirmed ? 'confirmed' : 'manual_review',
  reviewer: confirmed ? '创建申请验收员21' : '',
  reviewedAt: confirmed ? '2026-08-07T10:00:00.000Z' : '',
  status: confirmed ? 'confirmed' : 'selected',
  supplierCandidates: confirmed ? [{ supplierCode: `SUP-VERIFY-21-${index % 2}`,
    supplierName: `创建申请供应商${index % 2}`, quotePrice: 100 + index,
    quantity: index }] : [],
  priceEvidence: confirmed ? [{ supplierCode: `SUP-VERIFY-21-${index % 2}`,
    currentPrice: 100 + index, evidenceSource: 'QuoteComparison' }, {
    supplierCode: `SUP-VERIFY-21-${index % 2}`, historyPrice: 95 + index,
    evidenceSource: 'PriceReferenceContext' }] : [],
})
const scenario = (count, incomplete = 0) => {
  const result = { objectType: 'SupplierRecommendationDecisionBatchResult',
    batchId: `SRDB-VERIFY-21-${count}-${incomplete}`, decisionRevision: 1,
    status: incomplete ? 'reopen_review' : 'confirmed',
    items: Array.from({ length: count }, (_, index) => makeItem(index + 1,
      incomplete !== index + 1)), confirmedBy: '创建申请验收员21',
    confirmedAt: '2026-08-07T10:00:00.000Z', purchaseOrderCreated: false }
  const gate = evaluatePurchaseOrderCreationGateDecisionV1142820(
    createPurchaseOrderCreationGateDecisionV1142820({ decisionBatchResult: result,
      purchaseContext: { sourceRequestNos: ['PR-VERIFY-21'],
        sourceInquiryNos: ['PI-VERIFY-21'] } }),
    { checkedBy: 'Gate验收员21', now: '2026-08-07T10:05:00.000Z' })
  return { result, gate }
}
const create = input => createPurchaseOrderCreationRequestsV1142821({
  decisionBatchResult: input.result, gateDecision: input.gate,
  purchaseContext: input.gate.purchaseContext, createdBy: '创建申请验收员21',
  now: '2026-08-07T10:10:00.000Z',
})
const canaryAInput = scenario(1)
const canaryBInput = scenario(13)
const canaryCInput = scenario(3, 2)
const canaryA = create(canaryAInput)
const canaryB = create(canaryBInput)
let canaryCBlocked = false
try { create(canaryCInput) } catch { canaryCBlocked = true }

const current = run(['--test', 'tests/acceptance/purchaseOrderCreationRequestRuntimeV1142821.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/purchaseOrderGateRuntimeV1142820.test.mjs',
  'tests/acceptance/purchaseOrderGateAuditLoopV11428202.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const model = read('src/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderCreationRequestV1142821.js')
const provider = read('src/meta/providers/purchaseOrderCreationRequestProviderV1142821.js')
const page = read('src/meta/pages/ScmPurchaseOrderCreationRequestPage.vue')
const shellPage = read('src/meta/pages/ScmPage.vue')
const router = read('src/router/index.js')
const gateInput = [canaryAInput, canaryBInput].every(input =>
  input.gate.status === 'ready_for_purchase_order'
    && input.gate.sourceObjectType === 'SupplierRecommendationDecisionBatchResult')
  && provider.includes('purchaseOrderGateRuntimeProviderV1142820')
const creationRequest = current.status === 0 && canaryA.length === 1
  && canaryA[0].objectType === 'PurchaseOrderCreationRequest'
  && canaryB.reduce((count, request) => count + request.materialItems.length, 0) === 13
  && canaryCBlocked
  && ['requestId', 'sourceDecisionBatchId', 'supplierCode', 'supplierName', 'materialItems',
    'totalAmount', 'requestStatus', 'createdBy', 'createdAt'].every(field => model.includes(field))
const sourceTrace = [...canaryA, ...canaryB].every(request =>
  request.sourceObjectType === 'SupplierRecommendationDecisionBatchResult'
    && request.sourceTrace.gateStatus === 'ready_for_purchase_order'
    && request.sourceTrace.historicalPurchaseOrderReadCount === 0)
  && provider.includes("sourcePriority: freeze(['SupplierRecommendationDecisionBatchResult'])")
const batchCompleteness = canaryBInput.gate.batchCompleteness.totalItemCount === 13
  && canaryBInput.gate.batchCompleteness.pendingItemCount === 0
  && canaryB.flatMap(request => request.materialItems).length === 13
  && canaryCInput.gate.batchCompleteness.pendingItemCount === 1
const noPurchaseOrder = [...canaryA, ...canaryB].every(request =>
  !request.purchaseOrderCreated && !request.purchaseOrderSubmitted
    && !request.purchaseOrderApproved && request.downstreamWriteCount === 0)
  && !page.includes('CREATE_PURCHASE_ORDER')
  && !provider.includes('createScmPurchaseOrder')
const process011 = current.status === 0 && routeRegression.status === 0
  && router.includes("path: 'scm/purchase-order'")
  && shellPage.includes("route.path === '/scm/purchase-order'")
  && ['purchase-order-creation-request-page', 'creation-request-purchase-context',
    'creation-request-supplier', 'creation-request-material-items',
    'creation-request-evidence', 'creation-request-status',
    'GENERATE_PURCHASE_ORDER_CREATION_REQUEST'].every(value => page.includes(value))
  && model.includes("created: freeze(['reviewing', 'cancelled'])")
  && model.includes("reviewing: freeze(['approved_for_creation', 'cancelled'])")

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Gate Input', gateInput],
  ['Creation Request', creationRequest],
  ['Source Trace', sourceTrace],
  ['Batch Completeness', batchCompleteness],
  ['No PurchaseOrder', noPurchaseOrder],
  ['PROCESS-011', process011],
  ['Regression', regression.status === 0 && routeRegression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.21')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(`Canary A ${canaryA.length === 1 ? 'PASS' : 'FAIL'}`)
console.log(`Canary B ${canaryB.flatMap(request => request.materialItems).length === 13 ? 'PASS' : 'FAIL'}`)
console.log(`Canary C ${canaryCBlocked ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_PURCHASE_ORDER_CREATION_REQUEST_READY'
  : 'SCM_PURCHASE_ORDER_CREATION_REQUEST_ISSUES_FOUND')
if (!passed) process.exitCode = 1
