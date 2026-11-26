import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationBatchStoreV11428165 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationTaskStoreV11428167 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { createSupplierRecommendationDecisionBatchStoreV11428169,
  executeSupplierRecommendationDecisionBatchEntryV11428169 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { createSupplierRecommendationRouteContextResolverV11428171,
  SUPPLIER_RECOMMENDATION_PAGE_ROUTE_V11428171 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js'
import { resolveScmPurchaseProcessNodePageUrlV11428171 } from '../../src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => { const values = new Map(); return {
  getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }
const qualificationProvider = { source: 'Supplier Master', load: () => ({ options: [
  { supplierCode: 'SUP-ROUTE-A', supplierName: '路由验收供应商', supplierStatus: 'active' },
] }) }
const input = { priceApprovalId: 'PA-ROUTE-1', priceApprovalNo: 'PAP-ROUTE-1',
  sourceInquiryNo: 'PI-ROUTE-1', sourceRequestNo: 'PR-ROUTE-1',
  quoteComparisonId: 'QC-ROUTE-1', materialCode: 'MAT-ROUTE-1', materialName: '路由验收物料',
  supplierCandidates: [{ supplierCode: 'SUP-ROUTE-A', supplierName: '路由验收供应商', quotePrice: 100 }],
  priceEvidence: [{ supplierCode: 'SUP-ROUTE-A', currentPrice: 100, evidenceSource: 'QuoteComparison' }] }

function fixture() {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const batchStore = createSupplierRecommendationBatchStoreV11428165({ storage: memoryStorage() })
  const taskStore = createSupplierRecommendationTaskStoreV11428167({ storage: memoryStorage() })
  const decisionBatchStore = createSupplierRecommendationDecisionBatchStoreV11428169({ storage: memoryStorage() })
  const entry = executeSupplierRecommendationDecisionBatchEntryV11428169([input],
    { handoffStore, batchStore, taskStore, decisionBatchStore, qualificationProvider })
  const resolver = createSupplierRecommendationRouteContextResolverV11428171({
    storage: memoryStorage(), decisionBatchStore, taskStore })
  return { entry, resolver }
}

test('supplier quote and supplier recommendation expose stable page-only routes', () => {
  const router = read('src/router/index.js')
  assert.match(router, /path: 'scm\/supplier-quotes'/)
  assert.match(router, /path: 'scm\/supplier-recommendation'/)
  assert.match(router, /name: 'ScmSupplierRecommendation'/)
  assert.doesNotMatch(router, /supplier-recommendation-task\/:taskId/)
  assert.equal(SUPPLIER_RECOMMENDATION_PAGE_ROUTE_V11428171, '/scm/supplier-recommendation')
})

test('PriceApproval entry activates internal context and navigates without business data', () => {
  const source = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  assert.match(source, /supplierRecommendationRouteContextResolverV11428171\.activate\(result\.activeBatch\.batchId\)/)
  assert.match(source, /supplierRecommendationRouteContextResolverV11428171\.activate\(firstBatch\.batchId\)/)
  assert.match(source, /router\.push\(context\.pageRoute\)/)
  assert.doesNotMatch(source, /buildSupplierRecommendationEntryRouteV1142817/)
})

test('Context Resolver restores Task then DecisionBatch then DecisionItem internally', () => {
  const { entry, resolver } = fixture()
  assert.equal(entry.result, 'PASS')
  const activated = resolver.activate(entry.activeBatch.batchId)
  assert.equal(activated.result, 'PASS')
  assert.equal(activated.pageRoute, '/scm/supplier-recommendation')
  const restored = resolver.resolve()
  assert.equal(restored.result, 'PASS')
  assert.ok(restored.task.taskId)
  assert.equal(restored.decisionBatch.batchId, entry.activeBatch.batchId)
  assert.equal(restored.decisionItems.length, 1)
  assert.equal(restored.decisionItems[0].materialCode, 'MAT-ROUTE-1')
  assert.equal(restored.providerTaskId, entry.activeBatch.batchId)
})

test('Process Center and PriceApproval resolve the same page identity', () => {
  assert.equal(resolveScmPurchaseProcessNodePageUrlV11428171({ nodeCode: 'supplier-recommendation' }),
    '/scm/supplier-recommendation')
  const registry = read('src/meta/process/businessProcessRegistry.js')
  assert.match(registry, /resolveScmPurchaseProcessNodePageUrlV11428171\(node\)/)
  const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
  assert.match(page, /supplierRecommendationRouteContextResolverV11428171\.resolve\(\)/)
  assert.doesNotMatch(page, /route\.(?:params|query)/)
})

test('active page registrations contain no business-context route segment', () => {
  for (const file of ['src/meta/governance/businessNameRegistry.js',
    'src/meta/schema/scm/scmPageIdentityRegistry.js', 'src/meta/schema/scm/scmStandardPageContract.js',
    'src/meta/process/scmPageGovernanceComplianceV114281031.js',
    'src/meta/process/scmNodePageGovernanceV11428103.js',
    'src/meta/process/scm/supplierRecommendation/supplierRecommendationPageContractV1142811.js']) {
    const source = read(file)
    assert.match(source, /\/scm\/supplier-recommendation/)
    assert.doesNotMatch(source, /supplier-recommendation-task|:taskId/)
  }
  for (const protectedFile of [
    'src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js',
    'src/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js',
    'src/meta/runtime/supplierRecommendationActionRuntimeV1142811.js',
    'src/meta/pages/ScmPurchaseOrderGatePage.vue']) {
    assert.doesNotMatch(read(protectedFile), /V11428171|RouteContextResolverV11428171/)
  }
})
