import { canPerformAction } from '../runtime/permissionEngine.js'
import { executeReopenSupplierRecommendationDecisionItemV11428202,
  supplierRecommendationDecisionBatchStoreV11428169 } from '../process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { supplierRecommendationDataHandoffProviderV1142818 } from './supplierRecommendationDataHandoffProviderV1142818.js'
import { createPurchaseOrderCreationGateDecisionV1142820,
  evaluatePurchaseOrderCreationGateDecisionV1142820,
  purchaseOrderCreationGateDecisionStoreV1142820 } from '../process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateDecisionV1142820.js'
import { createPurchaseOrderGateInspectionRecordV11428202,
  purchaseOrderGateInspectionRecordStoreV11428202 } from '../process/scm/purchaseOrderCreationGate/purchaseOrderGateInspectionRecordV11428202.js'

export const PURCHASE_ORDER_GATE_RUNTIME_PROVIDER_VERSION_V1142820 = 'V1.14.2.8.18.20'
const freeze = value => Object.freeze(value)

const toRow = decision => freeze({
  gateNo: decision.gateDecisionId,
  recommendedSupplierName: decision.items.map(item => item.selectedSupplierName).filter(Boolean).join('、'),
  currency: '-',
  totalCost: '-',
  purchaseDetailCount: decision.items.length,
  sourceInquiryNo: (decision.purchaseContext?.sourceInquiryNos || []).join('、'),
  statusCode: decision.status,
  statusLabel: ({ pending_review: '待准入检查', blocked: '准入阻断',
    ready_for_purchase_order: '可进入采购订单' })[decision.status] || '状态待确认',
  blockedReasonLabel: decision.blockedReasons.join('、') || '无',
  recommendationEvidenceCount: decision.items.reduce((count, item) => count
    + item.quoteComparisonEvidence.length + item.supplierQuoteEvidence.length
    + item.historicalPriceEvidence.length, 0),
  recommendationBasis: decision.items.map(item => item.selectionReason).filter(Boolean).join('；'),
  confirmedBy: [...new Set(decision.items.map(item => item.reviewer).filter(Boolean))].join('、'),
  confirmedAt: [...new Set(decision.items.map(item => item.reviewedAt).filter(Boolean))].join('、'),
  comparisonEvidencePresent: decision.items.every(item => item.quoteComparisonEvidence.length > 0),
  purchaseOrderCreated: false,
  factScope: 'purchase_order_gate_decision_batch_result',
})

export function createPurchaseOrderGateRuntimeProviderV1142820({
  decisionBatchStore = supplierRecommendationDecisionBatchStoreV11428169,
  dataHandoffProvider = supplierRecommendationDataHandoffProviderV1142818,
  gateDecisionStore = purchaseOrderCreationGateDecisionStoreV1142820,
  inspectionRecordStore = purchaseOrderGateInspectionRecordStoreV11428202,
} = {}) {
  const source = () => {
    const batchId = decisionBatchStore.activeBatchId()
    const decisionBatchResult = batchId ? decisionBatchStore.findResult(batchId) : null
    const gateHandoff = batchId ? decisionBatchStore.findHandoff(batchId) : null
    if (!batchId || !decisionBatchResult
      || !['confirmed', 'reopen_review'].includes(decisionBatchResult.status)
      || !gateHandoff || !['handoff_ready', 'reopen_review'].includes(gateHandoff.status)) {
      return freeze({ result: 'FAIL', error: 'CONFIRMED_DECISION_BATCH_RESULT_NOT_FOUND',
        batchId, decisionBatchResult: null, handoffFacts: null })
    }
    const handoffFacts = dataHandoffProvider.load({ taskId: batchId })
    if (handoffFacts.result !== 'PASS') return freeze({ result: 'FAIL',
      error: handoffFacts.error || 'PURCHASE_ORDER_GATE_SOURCE_HANDOFF_INVALID', batchId,
      decisionBatchResult, handoffFacts })
    return freeze({ result: 'PASS', batchId, decisionBatchResult, gateHandoff, handoffFacts })
  }
  const draft = sourceFacts => createPurchaseOrderCreationGateDecisionV1142820({
    decisionBatchResult: sourceFacts.decisionBatchResult,
    purchaseContext: sourceFacts.handoffFacts.purchaseContext,
  })
  const evaluateAndRecord = (sourceFacts, { checkedBy, now } = {}) => {
    const decision = evaluatePurchaseOrderCreationGateDecisionV1142820(draft(sourceFacts), {
      now, checkedBy: checkedBy || sourceFacts.decisionBatchResult.confirmedBy
        || sourceFacts.decisionBatchResult.reopenedBy || 'gate-data-sync',
    })
    const savedDecision = gateDecisionStore.save(decision)
    const sequence = inspectionRecordStore.listByGateId(savedDecision.gateDecisionId).length + 1
    const inspectionRecord = inspectionRecordStore.save(
      createPurchaseOrderGateInspectionRecordV11428202(savedDecision, sequence))
    return freeze({ decision: savedDecision, inspectionRecord })
  }
  return freeze({
    providerCode: 'PurchaseOrderGateRuntimeProviderV1142820',
    sourcePriority: freeze(['SupplierRecommendationDecisionBatchResult',
      'SupplierRecommendationDecisionBatchGateHandoff', 'PriceApprovalRuntimeContext']),
    load() {
      const sourceFacts = source()
      if (sourceFacts.result !== 'PASS') return freeze({ ...sourceFacts, current: null,
        records: freeze([]), recordCount: 0,
        inspectionRecords: freeze(sourceFacts.batchId
          ? inspectionRecordStore.listByBatchId(sourceFacts.batchId) : []), businessWriteCount: 0,
        productionDataWritten: false, purchaseOrderCreated: false })
      const latestDraft = draft(sourceFacts)
      const previous = gateDecisionStore.findByBatchId(sourceFacts.batchId)
      const propagated = !previous || previous.sourceDecisionSignature !== latestDraft.sourceDecisionSignature
        ? evaluateAndRecord(sourceFacts) : null
      const current = propagated?.decision || previous
      const inspectionRecords = freeze(inspectionRecordStore.listByGateId(current.gateDecisionId))
      return freeze({ result: 'PASS', source: sourceFacts, current, records: freeze([toRow(current)]),
        recordCount: 1, inspectionRecords,
        latestInspectionRecord: inspectionRecords.at(-1) || null,
        decisionUpdatePropagated: Boolean(propagated),
        businessWriteCount: current.businessWriteCount,
        productionDataWritten: false, purchaseOrderCreated: false })
    },
    evaluateActive({ permissionContext = {}, now } = {}) {
      if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
        return freeze({ result: 'FAIL', error: 'ACTION_PERMISSION_DENIED',
          productionDataWritten: false, purchaseOrderCreated: false })
      }
      const sourceFacts = source()
      if (sourceFacts.result !== 'PASS') return freeze({ ...sourceFacts,
        productionDataWritten: false, purchaseOrderCreated: false })
      const previous = gateDecisionStore.findByBatchId(sourceFacts.batchId)
      const checkedBy = permissionContext.userName || permissionContext.user?.name
        || permissionContext.userId || permissionContext.role || 'gate-reviewer'
      const evaluated = evaluateAndRecord(sourceFacts, { now, checkedBy })
      return freeze({ result: 'PASS', decision: evaluated.decision,
        inspectionRecord: evaluated.inspectionRecord,
        refreshed: Boolean(previous),
        productionDataWritten: false, purchaseOrderCreated: false })
    },
    reopenMaterial(materialCode, { permissionContext = {}, now } = {}) {
      const sourceFacts = source()
      if (sourceFacts.result !== 'PASS') return freeze({ ...sourceFacts,
        productionDataWritten: false, purchaseOrderCreated: false })
      const result = executeReopenSupplierRecommendationDecisionItemV11428202(
        sourceFacts.batchId, materialCode, {}, { store: decisionBatchStore, permissionContext, now })
      return freeze({ ...result, productionDataWritten: false, purchaseOrderCreated: false })
    },
  })
}

export const purchaseOrderGateRuntimeProviderV1142820 =
  createPurchaseOrderGateRuntimeProviderV1142820()
