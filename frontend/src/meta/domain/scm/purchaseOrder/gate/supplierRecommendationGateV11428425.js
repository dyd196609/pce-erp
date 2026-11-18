export const SCM_SUPPLIER_RECOMMENDATION_GATE_VERSION_V11428425 = 'V1.14.2.8.4.25'

export const SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425 = Object.freeze({
  CREATED: 'CREATED',
  WAITING_CONFIRMATION: 'WAITING_CONFIRMATION',
  CONFIRMED: 'CONFIRMED',
  READY_FOR_PURCHASE_ORDER: 'READY_FOR_PURCHASE_ORDER',
  BLOCKED: 'BLOCKED',
})

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))
const unique = values => [...new Set(values.map(text).filter(Boolean))]

function selectedSupplier(item = {}) {
  return {
    supplierId: text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode),
    supplierName: text(item.selectedSupplierName || item.decisionSupplier?.supplierName),
  }
}

export function createSupplierRecommendationGateV11428425({
  decisionBatchResult = {}, purchaseContext = {}, handoff = {},
} = {}, now = new Date().toISOString()) {
  if (decisionBatchResult.objectType !== 'SupplierRecommendationDecisionBatchResult'
    || decisionBatchResult.status !== 'confirmed' || !text(decisionBatchResult.batchId)
    || !Array.isArray(decisionBatchResult.items) || !decisionBatchResult.items.length
    || !decisionBatchResult.items.every(item => item.objectType === 'SupplierRecommendationDecision')) {
    throw new Error('CONFIRMED_SUPPLIER_RECOMMENDATION_RESULT_REQUIRED')
  }
  const items = decisionBatchResult.items
  const suppliers = items.map(selectedSupplier)
  const supplierIds = unique(suppliers.map(item => item.supplierId))
  const supplierNames = unique(suppliers.map(item => item.supplierName))
  const quoteComparisonIds = unique(items.flatMap(item => item.quoteComparisonIds || []))
  const priceApprovalIds = unique([
    ...(purchaseContext.priceApprovalIds || []),
    ...items.flatMap(item => item.sourcePriceApprovalIds || []),
  ])
  const purchaseRequestIds = unique([
    ...(purchaseContext.sourceRequestIds || []), ...(purchaseContext.sourceRequestNos || []),
  ])
  const inquiryIds = unique([
    ...(purchaseContext.sourceInquiryIds || []), ...(purchaseContext.sourceInquiryNos || []),
  ])
  const quoteEvidence = items.flatMap(item => [
    ...(item.supplierCandidates || []), ...(item.quoteComparisonEvidence || []),
  ])
  const priceEvidence = items.flatMap(item => item.priceEvidence || [])
  const qualificationEvidence = items.flatMap(item => [
    ...(item.qualificationEvidence || []),
    ...(item.supplierCandidates || []).filter(candidate => candidate.qualificationStatus
      || candidate.qualificationEvidence),
  ])
  const decisionRevision = Number(decisionBatchResult.decisionRevision) || 0
  const recommendationDecisionId = text(handoff.resultId)
    || `SRDBR-${text(decisionBatchResult.batchId)}-R${decisionRevision}`
  const sourceSignature = [decisionBatchResult.batchId, decisionRevision,
    text(decisionBatchResult.confirmedAt), recommendationDecisionId].join('::')
  return freeze({
    objectType: 'SupplierRecommendationGate',
    sourceObjectType: 'SupplierRecommendationDecisionBatchResult',
    sourceDecisionObjectType: 'SupplierRecommendationDecision',
    gateId: `POG-${text(decisionBatchResult.batchId)}-R${decisionRevision}`,
    purchaseRequestId: purchaseRequestIds[0] || '',
    purchaseRequestIds: freeze(purchaseRequestIds),
    inquiryId: inquiryIds[0] || '',
    inquiryIds: freeze(inquiryIds),
    quoteComparisonId: quoteComparisonIds[0] || '',
    quoteComparisonIds: freeze(quoteComparisonIds),
    priceApprovalId: priceApprovalIds[0] || '',
    priceApprovalIds: freeze(priceApprovalIds),
    recommendedSupplierId: supplierIds[0] || '',
    recommendedSupplierIds: freeze(supplierIds),
    supplierName: supplierNames.join('、'),
    supplierNames: freeze(supplierNames),
    recommendationDecisionId,
    recommendationReason: unique(items.map(item => item.selectionReason
      || item.decisionReason)).join('；'),
    quoteEvidence: frozen(quoteEvidence),
    priceEvidence: frozen(priceEvidence),
    qualificationEvidence: frozen(qualificationEvidence),
    recommendationItems: frozen(items),
    sourceDecisionBatchId: text(decisionBatchResult.batchId),
    sourceDecisionRevision: decisionRevision,
    sourceDecisionStatus: text(decisionBatchResult.status),
    sourceConfirmedBy: text(decisionBatchResult.confirmedBy),
    sourceConfirmedAt: text(decisionBatchResult.confirmedAt),
    sourceSignature,
    status: SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.CREATED,
    statusLabel: '已创建',
    confirmedBy: '',
    confirmedAt: '',
    createdAt: now,
    updatedAt: now,
    purchaseOrderCreationAllowed: false,
    purchaseOrderCreationEntryReady: false,
    purchaseOrderCreated: false,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    automaticPurchaseOrderCreation: false,
    automaticSupplierSelection: false,
    productionDataWritten: false,
  })
}

export function prepareSupplierRecommendationGateV11428425(gate = {}, now = new Date().toISOString()) {
  if (gate.objectType !== 'SupplierRecommendationGate'
    || gate.status !== SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.CREATED) {
    throw new Error('SUPPLIER_RECOMMENDATION_GATE_CREATED_REQUIRED')
  }
  return freeze({ ...gate,
    status: SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.WAITING_CONFIRMATION,
    statusLabel: '等待人工确认', updatedAt: now })
}

export function confirmSupplierRecommendationGateV11428425(gate = {}, {
  confirmedBy = '', confirmedAt = new Date().toISOString(),
} = {}) {
  if (gate.objectType !== 'SupplierRecommendationGate'
    || gate.status !== SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.WAITING_CONFIRMATION
    || !text(confirmedBy)) {
    throw new Error('SUPPLIER_RECOMMENDATION_GATE_CONFIRMATION_NOT_ALLOWED')
  }
  return freeze({ ...gate,
    status: SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.CONFIRMED,
    statusLabel: '已人工确认', confirmedBy: text(confirmedBy), confirmedAt,
    updatedAt: confirmedAt, purchaseOrderCreationAllowed: false,
    purchaseOrderCreationEntryReady: false, purchaseOrderCreated: false })
}

export function createPurchaseOrderAdmissionContextV11428425(gate = {},
  now = new Date().toISOString()) {
  if (gate.objectType !== 'SupplierRecommendationGate'
    || gate.status !== SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.CONFIRMED) {
    throw new Error('CONFIRMED_SUPPLIER_RECOMMENDATION_GATE_REQUIRED')
  }
  return freeze({
    objectType: 'PurchaseOrderAdmissionContext',
    admissionContextId: `POAC-${gate.gateId}`,
    gateId: gate.gateId,
    sourceObjectType: gate.objectType,
    sourceDecisionBatchId: gate.sourceDecisionBatchId,
    sourceDecisionRevision: gate.sourceDecisionRevision,
    sourceSignature: gate.sourceSignature,
    purchaseRequestId: gate.purchaseRequestId,
    inquiryId: gate.inquiryId,
    quoteComparisonId: gate.quoteComparisonId,
    priceApprovalId: gate.priceApprovalId,
    recommendationDecisionId: gate.recommendationDecisionId,
    recommendedSupplierId: gate.recommendedSupplierId,
    supplierName: gate.supplierName,
    status: 'PENDING_CHECK',
    statusLabel: '等待准入检查',
    createdAt: now,
    purchaseOrderCreated: false,
    automaticPurchaseOrderCreation: false,
    productionDataWritten: false,
  })
}

export function createPurchaseOrderAdmissionResultV11428425(context = {}, gate = {}, guard = {},
  now = new Date().toISOString()) {
  if (context.objectType !== 'PurchaseOrderAdmissionContext'
    || gate.objectType !== 'SupplierRecommendationGate'
    || context.gateId !== gate.gateId || !Array.isArray(guard.checks)) {
    throw new Error('PURCHASE_ORDER_ADMISSION_CONTEXT_INVALID')
  }
  const ready = guard.result === 'PASS'
  return freeze({
    objectType: 'PurchaseOrderAdmissionResult',
    admissionResultId: `POAR-${gate.gateId}-${Date.parse(now) || 0}`,
    admissionContextId: context.admissionContextId,
    gateId: gate.gateId,
    sourceSignature: context.sourceSignature,
    checks: frozen(guard.checks),
    blockedReasons: frozen(guard.blockedReasons || []),
    status: ready ? SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.READY_FOR_PURCHASE_ORDER
      : SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.BLOCKED,
    statusLabel: ready ? '可进入采购订单创建' : '采购订单准入阻断',
    checkedBy: text(guard.checkedBy),
    checkedAt: now,
    purchaseOrderCreationAllowed: ready,
    purchaseOrderCreationEntryReady: ready,
    purchaseOrderCreated: false,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    automaticPurchaseOrderCreation: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function applyPurchaseOrderAdmissionResultV11428425(gate = {}, result = {}) {
  if (gate.objectType !== 'SupplierRecommendationGate'
    || gate.status !== SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.CONFIRMED
    || result.objectType !== 'PurchaseOrderAdmissionResult'
    || result.gateId !== gate.gateId
    || ![SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.READY_FOR_PURCHASE_ORDER,
      SUPPLIER_RECOMMENDATION_GATE_STATUS_V11428425.BLOCKED].includes(result.status)) {
    throw new Error('PURCHASE_ORDER_ADMISSION_RESULT_NOT_APPLICABLE')
  }
  return freeze({ ...gate, status: result.status, statusLabel: result.statusLabel,
    admissionResultId: result.admissionResultId, admissionCheckedBy: result.checkedBy,
    admissionCheckedAt: result.checkedAt,
    purchaseOrderCreationAllowed: result.purchaseOrderCreationAllowed,
    purchaseOrderCreationEntryReady: result.purchaseOrderCreationEntryReady,
    updatedAt: result.checkedAt, purchaseOrderCreated: false,
    automaticPurchaseOrderCreation: false })
}
