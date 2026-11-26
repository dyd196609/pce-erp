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
import { createPurchaseOrderGateInspectionRecordStoreV11428202,
  createPurchaseOrderGateInspectionRecordV11428202 } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderGateInspectionRecordV11428202.js'
import { createPurchaseOrderGateRuntimeProviderV1142820 } from '../../src/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js'

const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
}
const candidate = (code, price) => ({ supplierCode: code, supplierName: `供应商${code}`,
  quotePrice: price, priceRank: code === 'SUP-A' ? 1 : 2 })
const input = {
  priceApprovalId: 'PA-AUDIT-001', quoteComparisonId: 'QC-AUDIT-001',
  materialCode: 'MT-AUDIT', materialName: '审计物料',
  supplierCandidates: [candidate('SUP-A', 100), candidate('SUP-B', 108)],
  priceEvidence: [
    { supplierCode: 'SUP-A', currentPrice: 100, priceRank: 1, evidenceSource: 'QuoteComparison' },
    { supplierCode: 'SUP-B', currentPrice: 108, priceRank: 2, evidenceSource: 'QuoteComparison' },
  ],
}
const permissionContext = { role: 'manager', userName: 'Gate审计员' }

function setup() {
  const decisionBatchStore = createSupplierRecommendationDecisionBatchStoreV11428169({
    storage: memoryStorage(), storageKey: 'audit-batch',
  })
  const batch = createSupplierRecommendationDecisionBatchV11428169([input], 'SRDB-AUDIT-001')
  decisionBatchStore.saveBatch(batch)
  executeSelectDecisionBatchSupplierV11428169(batch.batchId, 'MT-AUDIT', 'SUP-A', '首次人工确认。',
    { store: decisionBatchStore, permissionContext })
  executeConfirmSupplierRecommendationDecisionBatchV11428169(batch.batchId,
    { confirmedBy: '采购确认员' }, { store: decisionBatchStore, permissionContext,
      now: '2026-08-06T14:00:00.000Z' })
  const gateDecisionStore = createPurchaseOrderCreationGateDecisionStoreV1142820({
    storage: memoryStorage(), storageKey: 'audit-gate',
  })
  const inspectionRecordStore = createPurchaseOrderGateInspectionRecordStoreV11428202({
    storage: memoryStorage(), storageKey: 'audit-inspections',
  })
  const provider = createPurchaseOrderGateRuntimeProviderV1142820({ decisionBatchStore,
    gateDecisionStore, inspectionRecordStore,
    dataHandoffProvider: { load: () => ({ result: 'PASS', purchaseContext: {
      sourceRequestNos: ['PR-AUDIT-001'], priceApprovalNos: ['PA-AUDIT-001'],
      sourceInquiryNos: ['PI-AUDIT-001'],
    } }) },
  })
  return { decisionBatchStore, gateDecisionStore, inspectionRecordStore, provider, batch }
}

test('Gate return modifies confirmed item through reopen_review to manual_review', () => {
  const { provider, decisionBatchStore, batch } = setup()
  const first = provider.evaluateActive({ permissionContext, now: '2026-08-06T14:10:00.000Z' })
  assert.equal(first.result, 'PASS')
  assert.equal(first.decision.status, 'ready_for_purchase_order')
  const reopened = provider.reopenMaterial('MT-AUDIT', { permissionContext,
    now: '2026-08-06T14:20:00.000Z' })
  assert.equal(reopened.result, 'PASS')
  assert.deepEqual(reopened.stateTransitions,
    ['confirmed -> reopen_review', 'reopen_review -> manual_review'])
  assert.equal(reopened.item.reviewStatus, 'manual_review')
  assert.equal(reopened.item.status, 'pending_manual_decision')
  assert.equal(decisionBatchStore.findResult(batch.batchId).status, 'reopen_review')
  assert.equal(decisionBatchStore.findHandoff(batch.batchId).status, 'reopen_review')
  assert.equal(decisionBatchStore.listReopenAudits(batch.batchId).length, 1)
})

test('reopened item can select another supplier, reconfirm, and pass Gate again', () => {
  const { provider, decisionBatchStore, batch } = setup()
  provider.evaluateActive({ permissionContext, now: '2026-08-06T14:10:00.000Z' })
  provider.reopenMaterial('MT-AUDIT', { permissionContext,
    now: '2026-08-06T14:20:00.000Z' })
  const selected = executeSelectDecisionBatchSupplierV11428169(batch.batchId, 'MT-AUDIT',
    'SUP-B', '退回后重新比较并改选供应商B。', { store: decisionBatchStore, permissionContext })
  assert.equal(selected.result, 'PASS')
  const reconfirmed = executeConfirmSupplierRecommendationDecisionBatchV11428169(batch.batchId,
    { confirmedBy: '采购复核员' }, { store: decisionBatchStore, permissionContext,
      now: '2026-08-06T14:30:00.000Z' })
  assert.equal(reconfirmed.result, 'PASS')
  assert.equal(reconfirmed.decisionBatchResult.items[0].selectedSupplierCode, 'SUP-B')
  const checked = provider.evaluateActive({ permissionContext, now: '2026-08-06T14:40:00.000Z' })
  assert.equal(checked.decision.status, 'ready_for_purchase_order')
  assert.equal(checked.decision.items[0].selectedSupplierCode, 'SUP-B')
  assert.equal(checked.purchaseOrderCreated, false)
})

test('Gate inspection records append immutable audit evidence and retain PASS/FAIL details', () => {
  const { provider, inspectionRecordStore } = setup()
  const first = provider.evaluateActive({ permissionContext, now: '2026-08-06T14:10:00.000Z' })
  const second = provider.evaluateActive({ permissionContext, now: '2026-08-06T14:11:00.000Z' })
  assert.equal(first.inspectionRecord.objectType, 'PurchaseOrderGateInspectionRecord')
  assert.equal(second.inspectionRecord.inspectionId.endsWith('002'), true)
  assert.equal(inspectionRecordStore.list().length, 2)
  assert.equal(second.inspectionRecord.checker, 'Gate审计员')
  assert.equal(second.inspectionRecord.checkResult, 'PASS')
  assert.equal(second.inspectionRecord.checkItems.length, 8)

  const blockedDraft = createPurchaseOrderCreationGateDecisionV1142820({
    decisionBatchResult: { objectType: 'SupplierRecommendationDecisionBatchResult',
      batchId: 'SRDB-BLOCKED-AUDIT', decisionRevision: 1, status: 'confirmed', items: [{ ...input,
        selectedSupplierCode: '', selectedSupplierName: '', selectionReason: '',
        reviewStatus: 'manual_review', reviewer: '', reviewedAt: '' }] },
    purchaseContext: {},
  })
  const blocked = evaluatePurchaseOrderCreationGateDecisionV1142820(blockedDraft,
    { checkedBy: 'Gate审计员', now: '2026-08-06T14:12:00.000Z' })
  const failRecord = createPurchaseOrderGateInspectionRecordV11428202(blocked, 1)
  assert.equal(failRecord.checkResult, 'FAIL')
  assert.ok(failRecord.blockReasons.length > 0)
  assert.ok(failRecord.checkItems.some(item => item.result === 'BLOCKED'))
  assert.equal(failRecord.purchaseOrderCreated, false)
})

test('Gate and supplier recommendation pages expose reopen, inspection, and audit contracts', async () => {
  const gatePage = await import('node:fs/promises').then(fs => fs.readFile(
    new URL('../../src/meta/pages/ScmPurchaseOrderGatePage.vue', import.meta.url), 'utf8'))
  const recommendationPage = await import('node:fs/promises').then(fs => fs.readFile(
    new URL('../../src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue', import.meta.url), 'utf8'))
  assert.match(gatePage, /gate-inspection-records/)
  assert.match(gatePage, /reopenMaterial/)
  assert.match(gatePage, /确认动作/)
  assert.match(gatePage, /检查动作/)
  assert.match(recommendationPage, /reopen_review/)
  assert.match(recommendationPage, /\['selected', 'confirmed'\]/)
  assert.doesNotMatch(gatePage, /createPurchaseOrder|savePurchaseOrder/)
})
