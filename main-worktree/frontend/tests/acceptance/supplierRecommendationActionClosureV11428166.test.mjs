import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createSupplierRecommendationCurrentSelectionV11428166 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationCurrentSelectionV11428166.js'
import { createSupplierRecommendationProcessCenterContextProviderV11428166 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationProcessCenterContextV11428166.js'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161,
  executePriceApprovalSupplierRecommendationHandoffV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationRealFactSourceV11428161,
  createSupplierRecommendationDecisionProviderV1142816 } from '../../src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { createSupplierRecommendationProviderV1142811 } from '../../src/meta/providers/supplierRecommendationProviderV1142811.js'
import { createSupplierRecommendationRuntimeStoreV1142811 } from '../../src/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'
import { executeConfirmRecommendationDecision, executeCreateRecommendationDecisionContext,
  executePreparePurchaseOrderGateHandoff, executePrepareRecommendationDecision,
  executeStartManualReview, executeStartRecommendationEvaluation } from '../../src/meta/runtime/supplierRecommendationActionRuntimeV1142811.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}
const supplierProvider = { source: 'Supplier Master', load: () => ({ options: [
  { supplierCode: 'SUP-A', supplierName: '供应商A', supplierStatus: 'active', source: 'Supplier Master' },
  { supplierCode: 'SUP-B', supplierName: '供应商B', supplierStatus: 'active', source: 'Supplier Master' },
] }) }
const input = {
  priceApprovalId: 'PA-ACTION-001', priceApprovalNo: 'PAP-ACTION-001',
  sourceInquiryNo: 'PI-ACTION-001', sourceRequestNo: 'PR-ACTION-001',
  quoteComparisonId: 'QC-ACTION-MAT-001', materialCode: 'MAT-ACTION-001', materialName: '动作闭环物料',
  supplierCandidates: [
    { supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 108, priceRank: 1 },
    { supplierCode: 'SUP-B', supplierName: '供应商B', quotePrice: 112, priceRank: 2 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-A', currentPrice: 108, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-B', currentPrice: 112, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
  historicalPriceEvidence: [
    { supplierCode: 'SUP-A', historyPrice: 100, currentPrice: 108, evidenceSource: 'PurchaseOrderHistory' },
    { supplierCode: 'SUP-B', historyPrice: 105, currentPrice: 112, evidenceSource: 'PurchaseOrderHistory' },
  ],
}

function buildFacts() {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  const handoff = executePriceApprovalSupplierRecommendationHandoffV11428161(
    input, handoffStore, supplierProvider).handoff
  const source = createSupplierRecommendationRealFactSourceV11428161({ priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] }, acceptanceModeResolver: () => false })
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const baseProvider = createSupplierRecommendationProviderV1142811({ sourceStore: source, store: runtimeStore })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource: source,
    quoteComparisonProvider: baseProvider, supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  return { handoff, runtimeStore, record: provider.load().records[0] }
}

test('candidate row action creates a current recommendation object bound to one runtime instance', () => {
  const { handoff } = buildFacts()
  const selection = createSupplierRecommendationCurrentSelectionV11428166({
    runtimeContext: handoff.runtimeContext,
    candidate: { ...input.supplierCandidates[1], materialCode: input.materialCode },
  }, '2026-08-06T10:00:00.000Z')
  assert.equal(selection.objectType, 'SupplierRecommendationCurrentSelection')
  assert.equal(selection.runtimeContextId, handoff.runtimeContext.runtimeContextNo)
  assert.equal(selection.materialCode, 'MAT-ACTION-001')
  assert.equal(selection.supplierCode, 'SUP-B')
  assert.equal(selection.supplierQuote, 112)
  assert.equal(selection.selectionMode, 'manual')
  assert.throws(() => createSupplierRecommendationCurrentSelectionV11428166({
    runtimeContext: handoff.runtimeContext,
    candidate: { supplierCode: 'SUP-A', materialCode: 'OTHER' },
  }), /INSTANCE_MISMATCH/)
})

test('one material exposes multiple supplier quotes and closes manual Decision plus Gate handoff', () => {
  const { handoff, record, runtimeStore } = buildFacts()
  assert.equal(record.materialCount, 1)
  assert.equal(record.supplierCount, 2)
  assert.deepEqual(record.preparation.comparisons.map(item => item.materialCode),
    ['MAT-ACTION-001', 'MAT-ACTION-001'])
  assert.deepEqual(record.preparation.comparisons.map(item => item.unitPrice), [108, 112])
  const selection = createSupplierRecommendationCurrentSelectionV11428166({
    runtimeContext: handoff.runtimeContext,
    candidate: { ...input.supplierCandidates[1], materialCode: input.materialCode },
  })
  const created = executeCreateRecommendationDecisionContext(record.preparation, runtimeStore, supplierProvider)
  const evaluating = executeStartRecommendationEvaluation(created.context, runtimeStore)
  const prepared = executePrepareRecommendationDecision(evaluating.context, runtimeStore)
  const reviewing = executeStartManualReview(prepared.context, runtimeStore)
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: selection.materialCode, supplierCode: selection.supplierCode }],
    reason: '人工比较两家供应商报价与历史价格后确认。', confirmedBy: '采购员验收166',
  }, runtimeStore)
  assert.equal(confirmed.decision.decisionStatus, 'confirmed')
  assert.equal(confirmed.decision.supplier[0].supplierCode, 'SUP-B')
  assert.ok(confirmed.decision.manualReviewedAt || confirmed.decision.manualConfirmedAt)
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, runtimeStore)
  assert.equal(gate.result, 'PASS')
  assert.equal(gate.handoff.purchaseOrderCreated, false)
})

test('process center route carries and restores the same validated RuntimeContextId', () => {
  const { handoff } = buildFacts()
  const storage = memoryStorage()
  const provider = createSupplierRecommendationProcessCenterContextProviderV11428166({
    storage, runtimeContextLoader: () => [handoff.runtimeContext],
  })
  assert.equal(provider.markActive(handoff.runtimeContext.runtimeContextNo).result, 'PASS')
  const url = provider.buildPageUrl()
  assert.match(url, /^\/scm\/supplier-recommendations\?runtimeContextId=/)
  assert.equal(decodeURIComponent(url.split('=')[1]), handoff.runtimeContext.runtimeContextNo)
  assert.equal(provider.resolveRuntimeContextId(), handoff.runtimeContext.runtimeContextNo)
  assert.equal(provider.markActive('PI-TEST-SR').result, 'FAIL')
  const empty = createSupplierRecommendationProcessCenterContextProviderV11428166({
    storage: memoryStorage(), runtimeContextLoader: () => [],
  })
  assert.equal(empty.buildPageUrl(), '')
})

test('page and SCM process registry expose action closure and material-supplier separation', () => {
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  const scmRegistry = read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js')
  const processRegistry = read('src/meta/process/businessProcessRegistry.js')
  for (const marker of ['SELECT_RECOMMENDATION_SUPPLIER', 'SupplierRecommendationCurrentSelection',
    'currentRecommendation', '推荐供应商', '推荐理由', '确认人', '确认时间',
    'CONFIRM_RECOMMENDATION_DECISION', '单物料供应商报价比较', '供应商报价']) {
    assert.ok(page.includes(marker))
  }
  const comparisonRegion = page.slice(page.indexOf('data-acceptance-region="comparison-evidence"'),
    page.indexOf('data-acceptance-region="historical-price-reference"'))
  assert.ok(comparisonRegion.includes('data-acceptance-id="single-material-summary"'))
  assert.ok(comparisonRegion.includes('prop="supplierName" label="供应商"'))
  assert.ok(!comparisonRegion.includes('prop="materialName" label="物料"'))
  assert.ok(scmRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428166'))
  assert.ok(processRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428166'))
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/meta/components/ProcessNodeNavigation.vue']) {
    assert.doesNotMatch(read(publicFile), /V11428166/)
  }
})
