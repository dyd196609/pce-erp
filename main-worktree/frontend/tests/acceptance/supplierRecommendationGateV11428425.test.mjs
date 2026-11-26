import test from 'node:test'
import assert from 'node:assert/strict'
import { createSupplierRecommendationGateV11428425,
  prepareSupplierRecommendationGateV11428425 } from '../../src/meta/domain/scm/purchaseOrder/gate/supplierRecommendationGateV11428425.js'
import { evaluatePurchaseOrderAdmissionGuardV11428425 } from '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderAdmissionGuardV11428425.js'
import { createSupplierRecommendationGateStoreV11428425,
  createPurchaseOrderAdmissionResultStoreV11428425,
  executeConfirmPurchaseOrderGateV11428425,
  executeEvaluatePurchaseOrderAdmissionV11428425 } from '../../src/meta/process/scm/purchaseOrderCreationGate/supplierRecommendationGateRuntimeV11428425.js'
import { buildPurchaseOrderCreationEntryHandoffV11428425 } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationEntryHandoffV11428425.js'
import { createSupplierRecommendationGateProviderV11428425 } from '../../src/meta/providers/supplierRecommendationGateProviderV11428425.js'

const item = ({ priceEvidence = true } = {}) => ({
  objectType: 'SupplierRecommendationDecision',
  decisionItemId: 'SRDI-PA-425-MAT-001',
  materialCode: 'MAT-001', materialName: '验收物料',
  sourcePriceApprovalIds: ['PAP-QC-425'], quoteComparisonIds: ['QC-425'],
  selectedSupplierCode: 'SUP-425', selectedSupplierName: '验收供应商',
  selectionReason: '采购员依据报价、核价和资格信息人工确认。',
  reviewStatus: 'confirmed', reviewer: '采购员甲',
  reviewedAt: '2026-08-07T09:00:00.000Z', status: 'confirmed',
  supplierCandidates: [{ supplierCode: 'SUP-425', supplierName: '验收供应商',
    quotationAmount: 125, qualificationStatus: 'qualified' }],
  priceEvidence: priceEvidence ? [{ supplierCode: 'SUP-425', currentPrice: 125,
    evidenceSource: 'PriceApprovalPreparation' }] : [],
})

const source = ({ priceEvidence = true } = {}) => ({
  decisionBatchResult: {
    objectType: 'SupplierRecommendationDecisionBatchResult', batchId: 'SRDB-425',
    decisionRevision: 1, status: 'confirmed', confirmedBy: '采购经理乙',
    confirmedAt: '2026-08-07T09:10:00.000Z', items: [item({ priceEvidence })],
    purchaseOrderCreated: false,
  },
  purchaseContext: { sourceRequestNos: ['PR-425'], sourceInquiryNos: ['PI-425'],
    priceApprovalIds: ['PAP-QC-425'] },
  handoff: { objectType: 'SupplierRecommendationDecisionBatchGateHandoff',
    batchId: 'SRDB-425', resultId: 'SRDBR-SRDB-425-R1', status: 'handoff_ready' },
})

const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value) }
}

test('真实推荐结果形成WAITING_CONFIRMATION Gate且Provider不写业务数据', () => {
  const facts = source()
  const gateStore = createSupplierRecommendationGateStoreV11428425({ storage: memoryStorage() })
  const provider = createSupplierRecommendationGateProviderV11428425({
    decisionBatchStore: {
      activeBatchId: () => 'SRDB-425', findResult: () => facts.decisionBatchResult,
      findHandoff: () => facts.handoff,
    },
    handoffProvider: { load: () => ({ result: 'PASS', purchaseContext: facts.purchaseContext }) },
    gateStore,
  })
  const loaded = provider.load()
  assert.equal(loaded.result, 'PASS')
  assert.equal(loaded.gate.objectType, 'SupplierRecommendationGate')
  assert.equal(loaded.gate.status, 'WAITING_CONFIRMATION')
  assert.equal(loaded.gate.purchaseRequestId, 'PR-425')
  assert.equal(loaded.gate.inquiryId, 'PI-425')
  assert.equal(loaded.gate.quoteComparisonId, 'QC-425')
  assert.equal(loaded.gate.priceApprovalId, 'PAP-QC-425')
  assert.equal(loaded.businessWriteCount, 0)
  assert.equal(loaded.purchaseOrderCreated, false)
})

test('ConfirmPurchaseOrderGate后准入通过只形成创建入口', () => {
  const facts = source()
  const gateStore = createSupplierRecommendationGateStoreV11428425({ storage: memoryStorage() })
  const resultStore = createPurchaseOrderAdmissionResultStoreV11428425({ storage: memoryStorage() })
  const waiting = prepareSupplierRecommendationGateV11428425(
    createSupplierRecommendationGateV11428425(facts), '2026-08-07T09:15:00.000Z')
  const confirmed = executeConfirmPurchaseOrderGateV11428425(waiting,
    { confirmedBy: '采购订单准入员丙' }, { gateStore, permissionContext: { role: 'manager' },
      now: '2026-08-07T09:20:00.000Z' })
  assert.equal(confirmed.result, 'PASS')
  assert.equal(confirmed.gate.status, 'CONFIRMED')
  const admitted = executeEvaluatePurchaseOrderAdmissionV11428425(confirmed.gate,
    { checkedBy: '采购订单准入员丙' }, { gateStore, resultStore,
      decisionBatchResult: facts.decisionBatchResult, permissionContext: { role: 'manager' },
      now: '2026-08-07T09:25:00.000Z' })
  assert.equal(admitted.result, 'PASS')
  assert.equal(admitted.guard.checks.length, 5)
  assert.equal(admitted.guard.result, 'PASS')
  assert.equal(admitted.admissionResult.status, 'READY_FOR_PURCHASE_ORDER')
  const entry = buildPurchaseOrderCreationEntryHandoffV11428425(admitted.admissionResult)
  assert.equal(entry.objectType, 'PurchaseOrderCreationEntry')
  assert.equal(entry.createActionExecuted, false)
  assert.equal(entry.purchaseOrderCreated, false)
  assert.equal(admitted.purchaseOrderCreated, false)
  assert.equal(admitted.productionDataWritten, false)
})

test('核价证据缺失时Guard阻断且不能形成采购订单入口', () => {
  const facts = source({ priceEvidence: false })
  const waiting = prepareSupplierRecommendationGateV11428425(
    createSupplierRecommendationGateV11428425(facts))
  const gateStore = createSupplierRecommendationGateStoreV11428425({ storage: memoryStorage() })
  const resultStore = createPurchaseOrderAdmissionResultStoreV11428425({ storage: memoryStorage() })
  const confirmed = executeConfirmPurchaseOrderGateV11428425(waiting,
    { confirmedBy: '采购订单准入员丙' }, { gateStore, permissionContext: { role: 'manager' } })
  const guard = evaluatePurchaseOrderAdmissionGuardV11428425({ gate: confirmed.gate,
    decisionBatchResult: facts.decisionBatchResult, checkedBy: '采购订单准入员丙' })
  assert.equal(guard.result, 'FAIL')
  assert.equal(guard.checks.find(value => value.checkCode === 'PRICE_APPROVAL_EVIDENCE_READY').result,
    'FAIL')
  const admitted = executeEvaluatePurchaseOrderAdmissionV11428425(confirmed.gate, {}, {
    gateStore, resultStore, decisionBatchResult: facts.decisionBatchResult,
    permissionContext: { role: 'manager' },
  })
  assert.equal(admitted.admissionResult.status, 'BLOCKED')
  assert.equal(admitted.admissionResult.purchaseOrderCreationAllowed, false)
  assert.throws(() => buildPurchaseOrderCreationEntryHandoffV11428425(admitted.admissionResult),
    /PURCHASE_ORDER_ADMISSION_READY_RESULT_REQUIRED/)
})

test('未人工确认Gate时不能执行准入检查', () => {
  const facts = source()
  const waiting = prepareSupplierRecommendationGateV11428425(
    createSupplierRecommendationGateV11428425(facts))
  const result = executeEvaluatePurchaseOrderAdmissionV11428425(waiting, {}, {
    gateStore: createSupplierRecommendationGateStoreV11428425({ storage: memoryStorage() }),
    resultStore: createPurchaseOrderAdmissionResultStoreV11428425({ storage: memoryStorage() }),
    decisionBatchResult: facts.decisionBatchResult, permissionContext: { role: 'manager' },
  })
  assert.equal(result.result, 'FAIL')
  assert.equal(result.error, 'CONFIRMED_SUPPLIER_RECOMMENDATION_GATE_REQUIRED')
  assert.equal(result.purchaseOrderCreated, false)
})
