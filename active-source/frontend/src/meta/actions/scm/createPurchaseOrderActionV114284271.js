import { assertPurchaseOrderCreationGuardV114284262 } from
  '../../domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js'
import { createGateGovernedPurchaseOrders } from '../../scm/scmStore.js'
import { canPerformAction } from '../../runtime/permissionEngine.js'
import { calculatePurchaseOrderQuantityV11428427112 } from
  '../../domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { buildSupplierPurchaseDraftsV11428427114,
  evaluateSupplierPurchaseDraftsV11428427114 } from
  '../../domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'
import { assertPurchaseOrderMaterialEligibilityV114284271144 } from
  '../../domain/scm/purchaseOrder/guard/purchaseOrderMaterialEligibilityGuardV114284271144.js'
import { evaluatePurchaseOrderCreationFinalCheckV114284271146 } from
  '../../domain/scm/purchaseOrder/domain/purchaseOrderCreationFinalCheckV114284271146.js'
import { createCanonicalPurchaseOrderNumberV11428427212 } from
  '../../runtime/purchaseOrderNumberRuntimeV11428427212.js'

export const CREATE_PURCHASE_ORDER_ACTION_VERSION_V114284271 = 'V1.14.2.8.4.27.1'
export const CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271 = 'CREATE_PURCHASE_ORDER'
export const PURCHASE_ORDER_ITEM_SOURCE_VERSION_V11428427111 = 'V1.14.2.8.4.27.1.1'
export const PURCHASE_ORDER_SUPPLIER_SPLIT_VERSION_V11428427114 = 'V1.14.2.8.4.27.1.4'
export const PURCHASE_ORDER_SUPPLIER_REAL_SPLIT_VERSION_V114284271143 =
  'V1.14.2.8.4.27.1.4.3'
export const PURCHASE_ORDER_MATERIAL_ELIGIBILITY_VERSION_V114284271144 =
  'V1.14.2.8.4.27.1.4.4'
export const PURCHASE_ORDER_CREATION_CONTEXT_VERSION_V114284271145 =
  'V1.14.2.8.4.27.1.4.5'
export const PURCHASE_ORDER_CREATION_FINAL_CHECK_VERSION_V114284271146 =
  'V1.14.2.8.4.27.1.4.6'

const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const safeId = value => text(value).replace(/[^A-Za-z0-9_-]/g, '-')

function blocked(error, reason = error) {
  return freeze({ success: false, result: 'BLOCKED', error, reason,
    businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false,
    purchaseOrderSubmitted: false, purchaseOrderApproved: false,
    purchaseOrderIssued: false, automaticPurchaseOrderCreation: false })
}

export function buildFormalPurchaseOrderV114284271({
  gate = {}, admissionResult = {}, draft = {}, supplierPurchaseDraft = {}, actor = '',
  now = new Date().toISOString(), sequence = 1,
} = {}) {
  const gateId = text(gate.gateId)
  const supplierId = text(supplierPurchaseDraft.supplierId)
  const supplierName = text(supplierPurchaseDraft.supplierName)
  const orderId = `po-gate-${safeId(gateId)}-${safeId(supplierId)}`
  const purchaseOrderNumber = createCanonicalPurchaseOrderNumberV11428427212({
    issuedAt: now, sequence,
  })
  const includedDraftItems = (draft.materialItems || []).filter(line =>
    number(line.confirmedQuantity ?? line.quantity) > 0
      && number(line.requestedQuantity) > 0
      && text(line.supplierId) === supplierId)
  const orderLines = includedDraftItems.map((line, index) => {
    const confirmedQuantity = number(line.confirmedQuantity ?? line.quantity)
    const confirmedPrice = number(line.confirmedPrice ?? line.unitPrice)
    const confirmedDeliveryDate = text(supplierPurchaseDraft.deliveryDate
      || line.confirmedDeliveryDate || draft.plannedDeliveryDate)
    return ({
    id: `${orderId}-line-${index + 1}`,
    lineNo: index + 1,
    materialId: text(line.materialId),
    materialCode: text(line.materialCode),
    materialName: text(line.materialName),
    sourcePurchaseRequestIds: [...new Set([
      ...(line.sourcePurchaseRequestIds || []), line.sourcePurchaseRequestId,
    ].map(text).filter(Boolean))],
    sourcePurchaseRequestId: text(line.sourcePurchaseRequestId
      || line.sourcePurchaseRequestIds?.[0] || gate.purchaseRequestId),
    sourceInquiryId: text(line.sourceInquiryId || gate.inquiryId),
    sourceQuoteComparisonId: text(line.sourceQuoteComparisonId || gate.quoteComparisonId),
    sourcePriceApprovalId: text(line.sourcePriceApprovalId || gate.priceApprovalId),
    requestedQuantity: number(line.requestedQuantity),
    availableQuantity: line.availableQuantity === null ? null : number(line.availableQuantity),
    orderedQuantity: line.orderedQuantity === null ? null : number(line.orderedQuantity),
    remainingQuantity: number(line.remainingQuantity),
    confirmedQuantity,
    originalSuggestedQuantity: number(line.originalSuggestedQuantity),
    quantityAdjustmentReason: text(line.quantityAdjustmentReason),
    quantityAdjustedBy: text(line.quantityAdjustedBy),
    quantityAdjustedAt: text(line.quantityAdjustedAt),
    quantityAdjustmentHistory: clone(line.quantityAdjustmentHistory || []),
    quantity: confirmedQuantity,
    supplierId, supplierName,
    supplierAllocationSource: text(line.supplierAllocationSource),
    quotedPrice: number(line.quotedPrice),
    approvedPrice: number(line.approvedPrice),
    confirmedPrice,
    price: confirmedPrice,
    planPrice: confirmedPrice,
    planAmount: Number((confirmedQuantity * confirmedPrice).toFixed(2)),
    requestedDate: text(line.requestedDate),
    supplierDeliveryDate: text(line.supplierDeliveryDate),
    confirmedDeliveryDate,
    plannedArrivalDate: confirmedDeliveryDate,
    remark: text(line.remark),
    sourceModule: 'supplierRecommendationGate',
    sourceOrderId: gateId,
    sourceOrderNo: gateId,
    sourceGateId: gateId,
    sourceRecommendationId: text(gate.recommendationDecisionId),
    confirmedBy: text(gate.confirmedBy),
    confirmedAt: text(gate.confirmedAt),
    confirmationSource: 'SupplierRecommendationGate',
    manualDataVersion: number(draft.manualDataVersion),
    itemDraftStatus: 'included',
    itemDraftStatusLabel: '纳入采购订单',
  })})
  const totalAmount = Number(orderLines.reduce((sum, line) => sum + line.planAmount, 0).toFixed(2))
  const purchaseOrder = {
    objectType: 'PurchaseOrder',
    classification: 'GATE_CREATED',
    id: orderId,
    objectNo: purchaseOrderNumber.objectNo,
    purchaseOrderNo: purchaseOrderNumber.objectNo,
    poNo: purchaseOrderNumber.objectNo,
    purchaseOrderNumberSource: purchaseOrderNumber.source,
    purchaseOrderNumberRule: purchaseOrderNumber.rule,
    sourceType: 'gate',
    sourceModule: 'supplierRecommendationGate',
    sourceId: gateId,
    sourceOrderId: gateId,
    sourceOrderNo: gateId,
    sourceGateId: gateId,
    sourceRecommendationId: text(gate.recommendationDecisionId),
    sourceInquiryId: text(gate.inquiryId),
    sourcePriceApprovalId: text(gate.priceApprovalId),
    sourceQuoteComparisonId: text(gate.quoteComparisonId),
    sourcePurchaseRequestIds: [...new Set([
      ...(draft.creationContext?.purchaseRequestIds || []),
      ...(draft.purchaseRequestIds || []), ...(gate.purchaseRequestIds || []),
      gate.purchaseRequestId,
    ].map(text).filter(Boolean))],
    supplierId, supplierName,
    confirmedBy: text(gate.confirmedBy),
    confirmedAt: text(gate.confirmedAt),
    confirmationSource: 'SupplierRecommendationGate',
    quoteEvidence: clone(gate.quoteEvidence || []),
    priceEvidence: clone(gate.priceEvidence || []),
    qualificationEvidence: clone(gate.qualificationEvidence || []),
    status: 'draft',
    lifecycleStatus: 'draft',
    orderStatus: 'draft',
    plannedArrivalDate: text(supplierPurchaseDraft.deliveryDate || draft.plannedDeliveryDate),
    totalAmount,
    planAmount: totalAmount,
    remark: text(supplierPurchaseDraft.supplierRemark || draft.remark),
    approvalOpinion: text(supplierPurchaseDraft.approvalRemark || draft.approvalOpinion),
    supplierPurchaseDraftId: text(supplierPurchaseDraft.supplierPurchaseDraftId),
    manualDataVersion: number(draft.manualDataVersion),
    gateSourceSignature: text(gate.sourceSignature),
    admissionResultId: text(admissionResult.admissionResultId),
    creationActionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
    createdBy: text(actor),
    createdAt: now,
    updatedAt: now,
  }
  return freeze({ purchaseOrder: freeze(clone(purchaseOrder)),
    orderLines: freeze(clone(orderLines)) })
}

export function buildFormalPurchaseOrdersV11428427114({
  gate = {}, admissionResult = {}, draft = {}, actor = '', now = new Date().toISOString(),
} = {}) {
  const supplierPurchaseDrafts = buildSupplierPurchaseDraftsV11428427114({ draft })
  return freeze(supplierPurchaseDrafts.map((supplierPurchaseDraft, index) =>
    buildFormalPurchaseOrderV114284271({ gate, admissionResult, draft,
      supplierPurchaseDraft, actor, now, sequence: index + 1 })))
}

export function executeCreatePurchaseOrderV114284271({
  actionCode = '', actor = '', gate = {}, admissionResult = {}, creationEntry = {},
  draft = {}, permissionContext = {}, now = new Date().toISOString(),
  repository = createGateGovernedPurchaseOrders,
} = {}) {
  if (actionCode !== CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271 || !text(actor)
    || !canPerformAction(permissionContext.role, 'EXECUTE')) {
    return blocked('EXPLICIT_CREATE_PURCHASE_ORDER_ACTION_REQUIRED')
  }
  const admission = assertPurchaseOrderCreationGuardV114284262({
    gate, admissionResult, creationEntry,
  })
  if (!admission.success) return blocked(admission.error, admission.reason)
  const sourceMaterialItems = draft.materialItems || []
  const materialEligibility = assertPurchaseOrderMaterialEligibilityV114284271144(
    sourceMaterialItems)
  if (!materialEligibility.success) return blocked(materialEligibility.error)
  const draftItems = materialEligibility.evaluation.eligibleItems
  const eligibleDraft = { ...draft, materialItems: draftItems,
    purchaseMaterialItems: draftItems,
    recommendationEvidenceItems: materialEligibility.evaluation.recommendationEvidenceItems }
  const quantityCalculations = draftItems.map(item =>
    calculatePurchaseOrderQuantityV11428427112(item))
  const includedItems = draftItems
  const supplierDraftEvaluation = evaluateSupplierPurchaseDraftsV11428427114(eligibleDraft)
  const sourceContractEnabled = includedItems.some(item =>
    Object.prototype.hasOwnProperty.call(item, 'sourcePurchaseRequestId'))
  const quantityModelEnabled = draftItems.some(item =>
    Object.prototype.hasOwnProperty.call(item, 'originalSuggestedQuantity'))
  const governedDraftEnabled = draft.objectType === 'PurchaseOrderDraft'
  if (supplierDraftEvaluation.result !== 'PASS') return blocked(
    supplierDraftEvaluation.missingFields.some(reason => reason.includes('同时分配给多个供应商'))
      ? 'PURCHASE_ORDER_ITEM_MULTI_SUPPLIER_ALLOCATION'
      : 'SUPPLIER_PURCHASE_DRAFT_INCOMPLETE',
    supplierDraftEvaluation.missingFields.join('；'))
  if (quantityModelEnabled) {
    const failed = quantityCalculations.filter(item => item.result !== 'PASS')
    if (failed.length) return blocked('PURCHASE_ORDER_QUANTITY_GUARD_BLOCKED',
      failed.flatMap(item => item.blockingReasons).join('；'))
  }
  if ((draft.objectType !== 'PurchaseOrderCreationDraft'
      && draft.objectType !== 'PurchaseOrderDraft')
    || (governedDraftEnabled && (draft.savedToStore !== true
      || draft.draftStatus !== 'ready_for_creation'
      || draft.readinessStatus !== 'ready_for_creation'))
    || draft.gateId !== gate.gateId
    || draft.admissionResultId !== admissionResult.admissionResultId
    || draft.sourceSignature !== gate.sourceSignature
    || number(draft.manualDataVersion) < 1
    || !Array.isArray(draft.materialItems) || !draft.materialItems.length
    || !includedItems.length
    || includedItems.some(item => !text(item.materialCode)
      || (sourceContractEnabled && (!text(item.sourcePurchaseRequestId || gate.purchaseRequestId)
        || !text(item.sourceInquiryId || gate.inquiryId)
        || !text(item.sourceQuoteComparisonId || gate.quoteComparisonId)
        || !text(item.sourcePriceApprovalId || gate.priceApprovalId)
        || !text(item.sourceGateId || gate.gateId)
        || number(item.requestedQuantity) <= 0
        || text(item.quantitySource) === 'UNKNOWN'))
      || number(item.confirmedQuantity ?? item.quantity) <= 0
      || number(item.confirmedPrice ?? item.unitPrice) < 0
      || number(item.requestedQuantity) <= 0
      || !text(item.supplierId)
      || !text(item.supplierName))) {
    return blocked('PURCHASE_ORDER_HUMAN_DRAFT_INCOMPLETE')
  }
  if (governedDraftEnabled
    && draft.finalCheckVersion === PURCHASE_ORDER_CREATION_FINAL_CHECK_VERSION_V114284271146) {
    const finalCheck = evaluatePurchaseOrderCreationFinalCheckV114284271146({
      gate, creationContext: draft.creationContext || {}, draft,
      entryGuard: admission.guard,
    })
    if (finalCheck.result !== 'PASS') {
      return blocked('PURCHASE_ORDER_CREATION_FINAL_CHECK_BLOCKED',
        finalCheck.checks.filter(item => item.result !== 'PASS')
          .map(item => `${item.checkName}：${item.reason}`).join('；'))
    }
  }
  const formalOrders = buildFormalPurchaseOrdersV11428427114({
    gate, admissionResult, draft: eligibleDraft, actor, now })
  const creationContext = { gate, admissionResult, creationEntry }
  const outcome = repository.length >= 2 && formalOrders.length === 1
    ? repository(formalOrders[0].purchaseOrder, formalOrders[0].orderLines,
      { creationContext })
    : repository(formalOrders, { creationContext })
  if (!outcome?.success) return blocked(outcome?.error || 'PURCHASE_ORDER_CREATE_FAILED')
  return freeze({ ...outcome,
    actionCode: CREATE_PURCHASE_ORDER_ACTION_CODE_V114284271,
    validMaterialCount: materialEligibility.evaluation.validMaterialCount,
    isolatedRecommendationEvidenceCount:
      materialEligibility.evaluation.evidenceOnlyCount,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    purchaseOrderIssued: false,
    automaticPurchaseOrderCreation: false,
  })
}
