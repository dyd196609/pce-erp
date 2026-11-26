import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createSupplierRecommendationDecisionBatchStoreV11428169,
  createSupplierRecommendationDecisionBatchV11428169,
  executeSelectDecisionBatchSupplierV11428169,
  executeConfirmSupplierRecommendationDecisionBatchV11428169,
} from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { createPurchaseOrderCreationGateDecisionStoreV1142820,
  createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820 } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'
import { createPurchaseOrderGateInspectionRecordStoreV11428202 } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderGateInspectionRecordV11428202.js'
import { createPurchaseOrderGateRuntimeProviderV1142820 } from '../../src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js'

const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
}
const permissionContext = { role: 'manager', userName: 'Gate同步验收员' }
const sourceInput = {
  priceApprovalId: 'PA-SYNC-001', quoteComparisonId: 'QC-SYNC-001',
  materialCode: 'MT-SYNC', materialName: '同步物料',
  supplierCandidates: [
    { supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 100, priceRank: 1 },
    { supplierCode: 'SUP-B', supplierName: '供应商B', quotePrice: 108, priceRank: 2 },
  ],
  priceEvidence: [
    { supplierCode: 'SUP-A', currentPrice: 100, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-B', currentPrice: 108, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
}

function setup() {
  const decisionBatchStore = createSupplierRecommendationDecisionBatchStoreV11428169({
    storage: memoryStorage(), storageKey: 'sync-batch',
  })
  const batch = createSupplierRecommendationDecisionBatchV11428169([sourceInput], 'SRDB-SYNC-001')
  decisionBatchStore.saveBatch(batch)
  executeSelectDecisionBatchSupplierV11428169(batch.batchId, 'MT-SYNC', 'SUP-A',
    '第一次人工选择供应商A。', { store: decisionBatchStore, permissionContext })
  const firstConfirmation = executeConfirmSupplierRecommendationDecisionBatchV11428169(batch.batchId,
    { confirmedBy: '采购员A' }, { store: decisionBatchStore, permissionContext,
      now: '2026-08-06T15:00:00.000Z' })
  const gateDecisionStore = createPurchaseOrderCreationGateDecisionStoreV1142820({
    storage: memoryStorage(), storageKey: 'sync-gate',
  })
  const inspectionRecordStore = createPurchaseOrderGateInspectionRecordStoreV11428202({
    storage: memoryStorage(), storageKey: 'sync-inspections',
  })
  const provider = createPurchaseOrderGateRuntimeProviderV1142820({ decisionBatchStore,
    gateDecisionStore, inspectionRecordStore,
    dataHandoffProvider: { load: () => ({ result: 'PASS', purchaseContext: {
      sourceRequestNos: ['PR-SYNC-001'], priceApprovalNos: ['PA-SYNC-001'],
      sourceInquiryNos: ['PI-SYNC-001'],
    } }) },
  })
  return { batch, decisionBatchStore, gateDecisionStore, inspectionRecordStore,
    provider, firstConfirmation }
}

test('Decision revisions append Supplier-A then Supplier-B without overwriting old result', () => {
  const { batch, decisionBatchStore, provider, firstConfirmation } = setup()
  assert.equal(firstConfirmation.decisionBatchResult.decisionRevision, 1)
  const firstGate = provider.load()
  assert.equal(firstGate.current.items[0].selectedSupplierCode, 'SUP-A')
  assert.equal(firstGate.current.sourceDecisionRevision, 1)
  provider.reopenMaterial('MT-SYNC', { permissionContext, now: '2026-08-06T15:10:00.000Z' })
  executeSelectDecisionBatchSupplierV11428169(batch.batchId, 'MT-SYNC', 'SUP-B',
    '退回后人工改选供应商B。', { store: decisionBatchStore, permissionContext })
  const secondConfirmation = executeConfirmSupplierRecommendationDecisionBatchV11428169(batch.batchId,
    { confirmedBy: '采购员B' }, { store: decisionBatchStore, permissionContext,
      now: '2026-08-06T15:20:00.000Z' })
  assert.equal(secondConfirmation.decisionBatchResult.decisionRevision, 2)
  const revisions = decisionBatchStore.listResultRevisions(batch.batchId)
  assert.deepEqual(revisions.map(item => item.decisionRevision), [1, 2])
  assert.deepEqual(revisions.map(item => item.items[0].selectedSupplierCode), ['SUP-A', 'SUP-B'])
})

test('Gate load propagates latest revision, ignores old Gate cache, and appends inspection history', () => {
  const { batch, decisionBatchStore, provider, inspectionRecordStore } = setup()
  const firstGate = provider.load()
  assert.equal(firstGate.decisionUpdatePropagated, true)
  assert.equal(firstGate.current.items[0].selectedSupplierCode, 'SUP-A')
  assert.equal(firstGate.inspectionRecords[0].inspectionId.endsWith('001'), true)
  assert.equal(firstGate.inspectionRecords[0].supplierSnapshot[0].supplierCode, 'SUP-A')

  provider.reopenMaterial('MT-SYNC', { permissionContext, now: '2026-08-06T15:10:00.000Z' })
  executeSelectDecisionBatchSupplierV11428169(batch.batchId, 'MT-SYNC', 'SUP-B',
    '退回后人工改选供应商B。', { store: decisionBatchStore, permissionContext })
  executeConfirmSupplierRecommendationDecisionBatchV11428169(batch.batchId,
    { confirmedBy: '采购员B' }, { store: decisionBatchStore, permissionContext,
      now: '2026-08-06T15:20:00.000Z' })
  const secondGate = provider.load()
  assert.equal(secondGate.decisionUpdatePropagated, true)
  assert.equal(secondGate.current.status, 'ready_for_purchase_order')
  assert.equal(secondGate.current.sourceDecisionRevision, 2)
  assert.equal(secondGate.current.items[0].selectedSupplierCode, 'SUP-B')
  assert.equal(secondGate.inspectionRecords.length, 2)
  assert.equal(secondGate.inspectionRecords[1].inspectionId.endsWith('002'), true)
  assert.deepEqual(inspectionRecordStore.list().map(item =>
    item.supplierSnapshot[0].supplierCode), ['SUP-A', 'SUP-B'])
  assert.equal(secondGate.purchaseOrderCreated, false)
})

test('reopened but unconfirmed result propagates a blocked Gate decision', () => {
  const { provider } = setup()
  provider.load()
  provider.reopenMaterial('MT-SYNC', { permissionContext, now: '2026-08-06T15:10:00.000Z' })
  const blocked = provider.load()
  assert.equal(blocked.result, 'PASS')
  assert.equal(blocked.current.status, 'blocked')
  assert.equal(blocked.current.sourceResultStatus, 'reopen_review')
  assert.ok(blocked.current.blockedReasons.includes('供应商推荐修改后尚未重新确认'))
  assert.equal(blocked.current.purchaseOrderCreationAllowed, false)
  assert.equal(blocked.purchaseOrderCreated, false)
})

test('missing DecisionRevision is blocked from Ready', () => {
  const draft = createPurchaseOrderCreationGateDecisionV1142820({ decisionBatchResult: {
    objectType: 'SupplierRecommendationDecisionBatchResult', batchId: 'SRDB-NO-REVISION',
    status: 'confirmed', confirmedAt: '2026-08-06T15:00:00.000Z', items: [{
      decisionItemId: 'ITEM-NO-REVISION', materialCode: 'MT-NO-REVISION', materialName: '缺版本物料',
      selectedSupplierCode: 'SUP-A', selectedSupplierName: '供应商A', selectionReason: '人工确认',
      reviewStatus: 'confirmed', reviewer: '采购员A', reviewedAt: '2026-08-06T15:00:00.000Z',
      supplierCandidates: [{ supplierCode: 'SUP-A', supplierName: '供应商A', quotePrice: 100 }],
      priceEvidence: [{ supplierCode: 'SUP-A', currentPrice: 100, evidenceSource: 'QuoteComparison' }],
    }],
  } })
  const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(draft,
    { checkedBy: 'Gate同步验收员', now: '2026-08-06T15:30:00.000Z' })
  assert.equal(decision.status, 'blocked')
  assert.equal(decision.checks.find(item => item.checkCode === 'DECISION_REVISION').result, 'BLOCKED')
  assert.equal(decision.purchaseOrderCreated, false)
})
