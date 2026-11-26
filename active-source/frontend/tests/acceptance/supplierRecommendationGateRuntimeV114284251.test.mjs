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

const memoryStorage = () => {
  const values = new Map()
  return { getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value) }
}

function source({ includePriceEvidence = true } = {}) {
  const decision = {
    objectType: 'SupplierRecommendationDecision',
    decisionItemId: 'SRDI-RUNTIME-251-MAT-001', decisionId: 'SRD-RUNTIME-251-MAT-001',
    materialCode: 'MAT-001', materialName: '真实承接验收物料',
    sourcePriceApprovalIds: ['PAP-QC-RUNTIME-251'], quoteComparisonIds: ['QC-RUNTIME-251'],
    selectedSupplierCode: 'SUP-RUNTIME-251', selectedSupplierName: '运行验收供应商',
    selectionReason: '采购人员依据报价比较与核价证据人工确认。',
    reviewStatus: 'confirmed', reviewer: '采购员运行验收',
    reviewedAt: '2026-08-08T08:00:00.000Z', status: 'confirmed',
    supplierCandidates: [{ supplierCode: 'SUP-RUNTIME-251', supplierName: '运行验收供应商',
      quotationAmount: 125, qualificationStatus: 'qualified' }],
    priceEvidence: includePriceEvidence ? [{ supplierCode: 'SUP-RUNTIME-251', currentPrice: 125,
      evidenceSource: 'PriceApprovalPreparation' }] : [],
  }
  return {
    decision,
    decisionBatchResult: { objectType: 'SupplierRecommendationDecisionBatchResult',
      batchId: 'SRDB-RUNTIME-251', decisionRevision: 1, status: 'confirmed',
      confirmedBy: '采购经理运行验收', confirmedAt: '2026-08-08T08:05:00.000Z',
      items: [decision], purchaseOrderCreated: false },
    purchaseContext: { sourceRequestNos: ['PR-RUNTIME-251'],
      sourceInquiryNos: ['PI-RUNTIME-251'], priceApprovalIds: ['PAP-QC-RUNTIME-251'] },
    handoff: { objectType: 'SupplierRecommendationDecisionBatchGateHandoff',
      batchId: 'SRDB-RUNTIME-251', resultId: 'SRDBR-SRDB-RUNTIME-251-R1',
      status: 'handoff_ready', purchaseOrderCreated: false },
  }
}

function runtime({ includePriceEvidence = true } = {}) {
  const facts = source({ includePriceEvidence })
  const gateStore = createSupplierRecommendationGateStoreV11428425({ storage: memoryStorage() })
  const resultStore = createPurchaseOrderAdmissionResultStoreV11428425({ storage: memoryStorage() })
  const provider = createSupplierRecommendationGateProviderV11428425({
    decisionBatchStore: { activeBatchId: () => facts.decisionBatchResult.batchId,
      findResult: () => facts.decisionBatchResult, findHandoff: () => facts.handoff },
    handoffProvider: { load: () => ({ result: 'PASS', purchaseContext: facts.purchaseContext }) },
    gateStore,
  })
  return { facts, gateStore, resultStore, provider }
}

test('Gate Provider只投影已存在SupplierRecommendationDecision并保留QC/PAP来源', () => {
  const { facts, provider } = runtime()
  const loaded = provider.load()
  assert.equal(loaded.result, 'PASS')
  assert.equal(loaded.factSource, 'SupplierRecommendationDecisionBatchResult')
  assert.equal(loaded.gate.sourceDecisionObjectType, 'SupplierRecommendationDecision')
  assert.equal(loaded.gate.recommendationItems[0].decisionId, facts.decision.decisionId)
  assert.equal(loaded.gate.quoteComparisonId, 'QC-RUNTIME-251')
  assert.equal(loaded.gate.priceApprovalId, 'PAP-QC-RUNTIME-251')
  assert.equal(loaded.businessWriteCount, 0)
})

test('Gate生命周期由人工动作从CREATED到CONFIRMED并由Guard进入READY', () => {
  const { facts, gateStore, resultStore } = runtime()
  const created = createSupplierRecommendationGateV11428425(facts,
    '2026-08-08T08:10:00.000Z')
  assert.equal(created.status, 'CREATED')
  const waiting = prepareSupplierRecommendationGateV11428425(created,
    '2026-08-08T08:11:00.000Z')
  const confirmed = executeConfirmPurchaseOrderGateV11428425(waiting,
    { confirmedBy: '准入检查员运行验收' }, { gateStore,
      permissionContext: { role: 'manager' }, now: '2026-08-08T08:12:00.000Z' })
  assert.equal(confirmed.gate.status, 'CONFIRMED')
  const admitted = executeEvaluatePurchaseOrderAdmissionV11428425(confirmed.gate,
    { checkedBy: '准入检查员运行验收' }, { gateStore, resultStore,
      decisionBatchResult: facts.decisionBatchResult, permissionContext: { role: 'manager' },
      now: '2026-08-08T08:13:00.000Z' })
  assert.equal(admitted.admissionResult.status, 'READY_FOR_PURCHASE_ORDER')
  assert.equal(admitted.gate.status, 'READY_FOR_PURCHASE_ORDER')
})

test('五项Guard均输出检查项、当前值、结果和原因', () => {
  const { facts, gateStore } = runtime()
  const waiting = prepareSupplierRecommendationGateV11428425(
    createSupplierRecommendationGateV11428425(facts))
  const confirmed = executeConfirmPurchaseOrderGateV11428425(waiting,
    { confirmedBy: '准入检查员运行验收' }, { gateStore, permissionContext: { role: 'manager' } })
  const guard = evaluatePurchaseOrderAdmissionGuardV11428425({ gate: confirmed.gate,
    decisionBatchResult: facts.decisionBatchResult, checkedBy: '准入检查员运行验收' })
  assert.equal(guard.checks.length, 5)
  for (const check of guard.checks) {
    assert.ok(check.checkName)
    assert.ok(check.currentValue)
    assert.match(check.result, /^(PASS|FAIL)$/)
    assert.ok(check.reason)
  }
  assert.deepEqual(guard.checks.map(item => item.result), ['PASS', 'PASS', 'PASS', 'PASS', 'PASS'])
})

test('缺核价证据进入BLOCKED且不能生成采购订单入口', () => {
  const { facts, gateStore, resultStore } = runtime({ includePriceEvidence: false })
  const waiting = prepareSupplierRecommendationGateV11428425(
    createSupplierRecommendationGateV11428425(facts))
  const confirmed = executeConfirmPurchaseOrderGateV11428425(waiting,
    { confirmedBy: '准入检查员运行验收' }, { gateStore, permissionContext: { role: 'manager' } })
  const admitted = executeEvaluatePurchaseOrderAdmissionV11428425(confirmed.gate, {}, {
    gateStore, resultStore, decisionBatchResult: facts.decisionBatchResult,
    permissionContext: { role: 'manager' },
  })
  assert.equal(admitted.admissionResult.status, 'BLOCKED')
  assert.equal(admitted.gate.status, 'BLOCKED')
  assert.equal(admitted.admissionResult.purchaseOrderCreated, false)
  assert.throws(() => buildPurchaseOrderCreationEntryHandoffV11428425(admitted.admissionResult),
    /PURCHASE_ORDER_ADMISSION_READY_RESULT_REQUIRED/)
})

test('PurchaseOrderCreationEntry仅导航且所有采购订单副作用保持关闭', () => {
  const { facts, gateStore, resultStore } = runtime()
  const waiting = prepareSupplierRecommendationGateV11428425(
    createSupplierRecommendationGateV11428425(facts))
  const confirmed = executeConfirmPurchaseOrderGateV11428425(waiting,
    { confirmedBy: '准入检查员运行验收' }, { gateStore, permissionContext: { role: 'manager' } })
  const admitted = executeEvaluatePurchaseOrderAdmissionV11428425(confirmed.gate, {}, {
    gateStore, resultStore, decisionBatchResult: facts.decisionBatchResult,
    permissionContext: { role: 'manager' },
  })
  const entry = buildPurchaseOrderCreationEntryHandoffV11428425(admitted.admissionResult)
  assert.equal(entry.entryRoute, '/scm/purchase-order')
  assert.equal(entry.createActionExecuted, false)
  assert.equal(entry.purchaseOrderCreated, false)
  assert.equal(entry.purchaseOrderSubmitted, false)
  assert.equal(entry.purchaseOrderApproved, false)
  assert.equal(entry.businessWriteCount, 0)
  assert.equal(entry.productionDataWritten, false)
})
