import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createPriceApprovalSupplierRecommendationHandoffStoreV11428161,
  executePriceApprovalSupplierRecommendationHandoffV11428161 } from '../../src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationRealFactSourceV11428161,
  createSupplierRecommendationDecisionProviderV1142816 } from '../../src/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { createSupplierRecommendationProviderV1142811 } from '../../src/meta/providers/supplierRecommendationProviderV1142811.js'
import { createPurchaseOrderGateHandoffProviderV11428161 } from '../../src/meta/providers/purchaseOrderGateHandoffProviderV11428161.js'
import { createSupplierRecommendationRuntimeStoreV1142811 } from '../../src/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'
import { resolveSupplierRecommendationEntryV11428163 } from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js'
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
const base = Object.freeze({ priceApprovalId: 'PA-MULTI-001', priceApprovalNo: 'PAP-MULTI-001',
  sourceInquiryNo: 'PI-REAL-MULTI-001', sourceRequestNo: 'PR-REAL-MULTI-001' })
const inputs = Object.freeze([
  Object.freeze({ ...base, quoteComparisonId: 'QC-MAT-A', materialCode: 'MAT-A', materialName: '物料A',
    supplierCandidates: [{ supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 110, priceRank: 1 }],
    priceEvidence: [{ supplierCode: 'SUP-A', currentPrice: 110, priceRank: 1 }],
    historicalPriceEvidence: [{ historyPrice: 100, currentPrice: 110, changeRate: 0.1 }] }),
  Object.freeze({ ...base, quoteComparisonId: 'QC-MAT-B', materialCode: 'MAT-B', materialName: '物料B',
    supplierCandidates: [{ supplierCode: 'SUP-B', supplierName: '供应商B', quotePrice: 220, priceRank: 1 }],
    priceEvidence: [{ supplierCode: 'SUP-B', currentPrice: 220, priceRank: 1 }],
    historicalPriceEvidence: [{ historyPrice: 200, currentPrice: 220, changeRate: 0.1 }] }),
])

function buildFacts() {
  const handoffStore = createPriceApprovalSupplierRecommendationHandoffStoreV11428161({ storage: memoryStorage() })
  for (const input of inputs) assert.equal(executePriceApprovalSupplierRecommendationHandoffV11428161(
    input, handoffStore, supplierProvider).result, 'PASS')
  const source = createSupplierRecommendationRealFactSourceV11428161({ priceApprovalHandoffStore: handoffStore,
    quoteComparisonStore: { listRecommendationPreparations: () => [] }, acceptanceModeResolver: () => false })
  const runtimeStore = createSupplierRecommendationRuntimeStoreV1142811({ storage: memoryStorage() })
  const baseProvider = createSupplierRecommendationProviderV1142811({ sourceStore: source, store: runtimeStore })
  const provider = createSupplierRecommendationDecisionProviderV1142816({ realFactSource: source,
    quoteComparisonProvider: baseProvider, supplierQualificationProvider: supplierProvider,
    priceReferenceContextProvider: { load: () => ({ records: [] }) } })
  return { handoffStore, source, runtimeStore, provider, records: provider.load().records }
}

test('PriceApproval handoff creates a complete SupplierRecommendationRuntimeContext', () => {
  const { handoffStore } = buildFacts()
  const contexts = handoffStore.listRuntimeContexts()
  assert.equal(contexts.length, 2)
  assert.equal(contexts[1].objectType, 'SupplierRecommendationRuntimeContext')
  for (const field of ['priceApprovalNo', 'priceApprovalId', 'quoteComparisonId', 'materialCode',
    'materialName', 'supplierCandidates', 'priceEvidence', 'historicalPriceEvidence']) assert.ok(contexts[1][field])
  assert.equal(contexts[1].materialCode, 'MAT-B')
  assert.equal(contexts[1].supplierCandidates[0].supplierCode, 'SUP-B')
})

test('composite entry key locks the requested material when the PriceApproval is shared', () => {
  const { records } = buildFacts()
  const routeEntry = { priceApprovalId: 'PA-MULTI-001', quoteComparisonId: 'QC-MAT-B', materialCode: 'MAT-B' }
  const resolved = resolveSupplierRecommendationEntryV11428163(records, routeEntry)
  assert.equal(resolved.result, 'PASS')
  assert.equal(resolved.record.runtimeContext.materialName, '物料B')
  assert.equal(resolved.record.runtimeContext.supplierCandidates[0].supplierCode, 'SUP-B')
  assert.equal(resolved.record.runtimeContext.priceEvidence[0].currentPrice, 220)
  assert.equal(resolveSupplierRecommendationEntryV11428163(records,
    { priceApprovalId: 'PA-MULTI-001' }).result, 'FAIL')
  assert.equal(resolveSupplierRecommendationEntryV11428163([records[1], records[1]], routeEntry).result, 'FAIL')
})

test('production source never creates or falls through to PI-TEST-SR', () => {
  const source = createSupplierRecommendationRealFactSourceV11428161({
    priceApprovalHandoffStore: { listPreparations: () => [] },
    quoteComparisonStore: { listRecommendationPreparations: () => [] },
    acceptanceFacts: [{ sourceInquiryNo: 'PI-TEST-SR' }], acceptanceModeResolver: () => false,
  })
  assert.deepEqual(source.listRecommendationPreparations(), [])
})

test('locked instance completes manual Decision and Gate handoff without a PurchaseOrder', () => {
  const { records, runtimeStore } = buildFacts()
  const current = resolveSupplierRecommendationEntryV11428163(records, {
    priceApprovalId: 'PA-MULTI-001', quoteComparisonId: 'QC-MAT-B', materialCode: 'MAT-B',
  }).record
  const created = executeCreateRecommendationDecisionContext(current.preparation, runtimeStore, supplierProvider)
  const evaluating = executeStartRecommendationEvaluation(created.context, runtimeStore)
  const prepared = executePrepareRecommendationDecision(evaluating.context, runtimeStore)
  const reviewing = executeStartManualReview(prepared.context, runtimeStore)
  const confirmed = executeConfirmRecommendationDecision(reviewing.context, reviewing.approvalContext, {
    selections: [{ materialCode: 'MAT-B', supplierCode: 'SUP-B' }],
    reason: '根据物料B当前报价和历史价格证据人工确认。', confirmedBy: '采购员王五',
  }, runtimeStore)
  assert.equal(confirmed.decision.decisionStatus, 'confirmed')
  assert.equal(confirmed.decision.material[0].materialCode, 'MAT-B')
  assert.equal(confirmed.decision.supplier[0].supplierCode, 'SUP-B')
  const gate = executePreparePurchaseOrderGateHandoff(confirmed.decision, runtimeStore)
  assert.equal(gate.result, 'PASS')
  const gateRecord = createPurchaseOrderGateHandoffProviderV11428161({ gateContextLoader: () => [],
    gateDecisionLoader: () => [], recommendationStore: runtimeStore }).load().current
  assert.equal(gateRecord.recommendedSupplierName, '供应商B')
  assert.equal(gateRecord.purchaseOrderCreated, false)
})

test('route and page business area enforce the same composite instance', () => {
  const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
  const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
  const router = read('src/router/index.js')
  for (const field of ['priceApprovalId:row.priceApprovalId', 'quoteComparisonId:row.quoteComparisonId',
    'materialCode:row.materialCode']) assert.ok(pricePage.includes(field))
  assert.match(page, /resolveSupplierRecommendationEntryV11428163/)
  assert.match(page, /item\.entryKey === entryResolution\.value\.entryKey/)
  assert.match(page, /placeholder="由采购核价入口锁定业务实例" disabled/)
  assert.ok(router.includes("path: 'scm/supplier-recommendations'"))
  assert.match(page, /data-page-code="supplier-recommendation"/)
  for (const publicFile of ['src/meta/components/PceListPageShell.vue',
    'src/meta/components/PceEnterpriseListTable.vue', 'src/router/index.js']) {
    assert.doesNotMatch(read(publicFile), /V11428163/)
  }
})
