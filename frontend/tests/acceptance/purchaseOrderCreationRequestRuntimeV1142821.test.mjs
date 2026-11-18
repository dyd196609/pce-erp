import test from 'node:test'
import assert from 'node:assert/strict'
import { createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820,
} from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'
import { createPurchaseOrderCreationRequestStoreV1142821,
  createPurchaseOrderCreationRequestsV1142821,
  transitionPurchaseOrderCreationRequestV1142821,
} from '../../src/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderCreationRequestV1142821.js'
import { createPurchaseOrderCreationRequestProviderV1142821,
} from '../../src/meta/providers/purchaseOrderCreationRequestProviderV1142821.js'

const makeItem = (index, confirmed = true) => ({
  decisionItemId: `SRDI-21-${index}`, materialCode: `MAT-21-${index}`,
  materialName: `创建申请验收物料${index}`, quantity: index + 1,
  sourcePriceApprovalIds: [`PA-21-${index}`], quoteComparisonIds: [`QC-21-${index}`],
  selectedSupplierCode: confirmed ? `SUP-21-${index % 2}` : '',
  selectedSupplierName: confirmed ? `创建申请供应商${index % 2}` : '',
  selectionReason: confirmed ? `采购员完成物料${index}报价及资格证据复核` : '',
  reviewStatus: confirmed ? 'confirmed' : 'manual_review',
  reviewer: confirmed ? '采购申请验收员21' : '',
  reviewedAt: confirmed ? '2026-08-07T09:00:00.000Z' : '',
  status: confirmed ? 'confirmed' : 'selected',
  supplierCandidates: confirmed ? [{ supplierCode: `SUP-21-${index % 2}`,
    supplierName: `创建申请供应商${index % 2}`, quotePrice: 100 + index,
    quantity: index + 1 }] : [],
  priceEvidence: confirmed ? [{ supplierCode: `SUP-21-${index % 2}`,
    currentPrice: 100 + index, evidenceSource: 'QuoteComparison' }, {
    supplierCode: `SUP-21-${index % 2}`, historyPrice: 95 + index,
    evidenceSource: 'PriceReferenceContext' }] : [],
})

const source = (count, incomplete = 0) => {
  const items = Array.from({ length: count }, (_, index) => makeItem(index + 1,
    incomplete !== index + 1))
  const result = { objectType: 'SupplierRecommendationDecisionBatchResult',
    batchId: `SRDB-21-${count}-${incomplete}`, decisionRevision: 1,
    status: incomplete ? 'reopen_review' : 'confirmed', items,
    confirmedBy: '采购申请验收员21', confirmedAt: '2026-08-07T09:00:00.000Z',
    purchaseOrderCreated: false }
  const draft = createPurchaseOrderCreationGateDecisionV1142820({
    decisionBatchResult: result,
    purchaseContext: { sourceRequestNos: ['PR-21'], sourceInquiryNos: ['PI-21'] },
  })
  const gate = evaluatePurchaseOrderCreationGateDecisionV1142820(draft, {
    checkedBy: 'Gate验收员21', now: '2026-08-07T09:10:00.000Z',
  })
  return { result, gate }
}

test('Canary A creates one request from one confirmed material without creating a PO', () => {
  const input = source(1)
  const requests = createPurchaseOrderCreationRequestsV1142821({
    decisionBatchResult: input.result, gateDecision: input.gate,
    purchaseContext: input.gate.purchaseContext, createdBy: '采购申请验收员21',
    now: '2026-08-07T09:20:00.000Z',
  })
  assert.equal(requests.length, 1)
  assert.equal(requests[0].materialItems.length, 1)
  assert.equal(requests[0].sourceObjectType, 'SupplierRecommendationDecisionBatchResult')
  assert.equal(requests[0].sourceTrace.gateId, input.gate.gateDecisionId)
  assert.equal(requests[0].purchaseOrderCreated, false)
})

test('Canary B retains all 13 DecisionItems and groups requests only by selected supplier', () => {
  const input = source(13)
  const requests = createPurchaseOrderCreationRequestsV1142821({
    decisionBatchResult: input.result, gateDecision: input.gate,
    purchaseContext: input.gate.purchaseContext, createdBy: '采购申请验收员21',
  })
  assert.equal(requests.length, 2)
  assert.equal(requests.reduce((sum, request) => sum + request.materialItems.length, 0), 13)
  assert.equal(new Set(requests.flatMap(request => request.materialItems)
    .map(item => item.materialCode)).size, 13)
  assert.ok(requests.every(request => request.totalAmount > 0))
})

test('Canary C blocks incomplete recommendation results and creates no request', () => {
  const input = source(3, 2)
  assert.equal(input.gate.status, 'blocked')
  assert.throws(() => createPurchaseOrderCreationRequestsV1142821({
    decisionBatchResult: input.result, gateDecision: input.gate,
  }), /CONFIRMED_DECISION_BATCH_RESULT_REQUIRED/)
})

test('provider persists requests, restores them, and status transitions never create a PO', () => {
  const input = source(1)
  const store = createPurchaseOrderCreationRequestStoreV1142821({ storage: null })
  store.clear()
  const gateProvider = { load: () => ({ result: 'PASS', current: input.gate,
    source: { batchId: input.result.batchId, decisionBatchResult: input.result,
      handoffFacts: { purchaseContext: input.gate.purchaseContext } } }) }
  const provider = createPurchaseOrderCreationRequestProviderV1142821({ gateProvider,
    requestStore: store })
  const created = provider.createActive({ permissionContext: { role: 'manager',
    userName: '采购申请验收员21' }, now: '2026-08-07T09:20:00.000Z' })
  assert.equal(created.result, 'PASS')
  assert.equal(provider.load().requestCount, 1)
  const reviewing = transitionPurchaseOrderCreationRequestV1142821(created.requests[0],
    'reviewing', { permissionContext: { role: 'manager', userName: '审核员21' } })
  const approved = transitionPurchaseOrderCreationRequestV1142821(reviewing,
    'approved_for_creation', { permissionContext: { role: 'manager', userName: '审核员21' } })
  assert.equal(approved.requestStatus, 'approved_for_creation')
  assert.equal(approved.purchaseOrderCreated, false)
  assert.equal(approved.downstreamWriteCount, 0)
})
