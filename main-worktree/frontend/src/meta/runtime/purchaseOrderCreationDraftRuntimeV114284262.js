import { calculatePurchaseOrderQuantityV11428427112 } from
  '../domain/scm/purchaseOrder/domain/purchaseOrderQuantityModelV11428427112.js'
import { buildSupplierPurchaseDraftsV11428427114,
  evaluateSupplierPurchaseDraftsV11428427114,
  synchronizeSupplierPurchaseDraftsV11428427114 } from
  '../domain/scm/purchaseOrder/domain/supplierPurchaseDraftModelV11428427114.js'
import { evaluatePurchaseOrderMaterialEligibilityV114284271144 } from
  '../domain/scm/purchaseOrder/guard/purchaseOrderMaterialEligibilityGuardV114284271144.js'
import { CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146 } from
  '../domain/scm/purchaseOrder/domain/purchaseOrderCreationFinalCheckV114284271146.js'

export const PURCHASE_ORDER_CREATION_DRAFT_RUNTIME_VERSION_V114284262 = 'V1.14.2.8.4.26.2'
export const PURCHASE_ORDER_DRAFT_RUNTIME_VERSION_V11428427113 = 'V1.14.2.8.4.27.1.3'
export const PURCHASE_ORDER_SUPPLIER_DRAFT_RUNTIME_VERSION_V11428427114 = 'V1.14.2.8.4.27.1.4'
export const PURCHASE_ORDER_SUPPLIER_REAL_SPLIT_RUNTIME_VERSION_V114284271143 =
  'V1.14.2.8.4.27.1.4.3'
export const PURCHASE_ORDER_DRAFT_RUNTIME_SOURCE_VERSION_V1142842711431 =
  'V1.14.2.8.4.27.1.4.3.1'
export const PURCHASE_ORDER_MATERIAL_ELIGIBILITY_RUNTIME_VERSION_V114284271144 =
  'V1.14.2.8.4.27.1.4.4'
export const PURCHASE_ORDER_CREATION_CONTEXT_RUNTIME_VERSION_V114284271145 =
  'V1.14.2.8.4.27.1.4.5'
export const PURCHASE_ORDER_CREATION_DRAFT_STORAGE_KEY_V114284262 =
  'pce.scm.purchase-order-creation-draft.v114284262'
export const SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262 =
  'SAVE_PURCHASE_ORDER_CREATION_DRAFT'
export const CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113 =
  'CONFIRM_PURCHASE_ORDER_DRAFT_FOR_CREATION'
export const PURCHASE_ORDER_DRAFT_STATUSES_V11428427113 = Object.freeze([
  'editing', 'confirmed', 'ready_for_creation',
])

const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryDrafts = []

const first = value => Array.isArray(value) ? value.find(item => text(item)) : value
const compositeSupplierName = value => /[、，,；;]/.test(text(value))

function selectedCandidate(item = {}) {
  const selectedCode = text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode)
  return (item.supplierCandidates || []).find(value =>
    text(value.supplierCode || value.supplierId) === selectedCode) || {}
}

function quotePrice(item = {}) {
  const selectedCode = text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode)
  const candidate = (item.supplierCandidates || []).find(value =>
    text(value.supplierCode) === selectedCode) || {}
  return number(candidate.quotePrice ?? candidate.quotationAmount
    ?? item.decisionSupplier?.quotePrice ?? item.selectedPrice)
}

function materialQuantity(item = {}) {
  return number(item.quantity ?? item.requestedQuantity
    ?? item.material?.quantity ?? item.materialLine?.quantity)
}

function sourceLine(gate = {}, item = {}, index = 0) {
  const candidate = selectedCandidate(item)
  const requestedQuantity = materialQuantity(item)
  const orderedQuantity = item.orderedQuantity === undefined ? null : number(item.orderedQuantity)
  const remainingQuantity = item.remainingQuantity === undefined
    ? (orderedQuantity === null ? requestedQuantity : Math.max(requestedQuantity - orderedQuantity, 0))
    : number(item.remainingQuantity)
  const singleGateSupplier = (gate.recommendedSupplierIds || []).length <= 1
  const supplierId = text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode
    || candidate.supplierCode || candidate.supplierId
    || (singleGateSupplier ? gate.recommendedSupplierId : ''))
  const supplierName = text(item.selectedSupplierName || item.decisionSupplier?.supplierName
    || candidate.supplierName || (singleGateSupplier ? gate.supplierName : ''))
  const quotedPrice = number(candidate.quotePrice ?? candidate.quotationAmount
    ?? item.decisionSupplier?.quotePrice ?? item.selectedPrice)
  const approvedPrice = number(item.approvedPrice ?? item.selectedPrice
    ?? item.decisionSupplier?.approvedPrice ?? quotedPrice)
  const sourcePurchaseRequestIds = [...new Set([
    ...(item.sourcePurchaseRequestIds || []), ...(item.sourceRequestIds || []),
    gate.purchaseRequestId,
  ].map(text).filter(Boolean))]
  return {
    lineNo: index + 1,
    sourcePurchaseRequestIds,
    sourcePurchaseRequestId: sourcePurchaseRequestIds[0] || '',
    sourceInquiryId: text(first(item.sourceInquiryIds) || gate.inquiryId),
    sourceQuoteComparisonId: text(first(item.quoteComparisonIds) || gate.quoteComparisonId),
    sourcePriceApprovalId: text(first(item.sourcePriceApprovalIds) || gate.priceApprovalId),
    sourceGateId: text(gate.gateId),
    materialId: text(item.materialId || item.material?.materialId),
    materialCode: text(item.materialCode || item.material?.materialCode),
    materialName: text(item.materialName || item.material?.materialName),
    requestedQuantity,
    quantitySource: ['quantity', 'requestedQuantity'].some(field =>
      Object.prototype.hasOwnProperty.call(item, field))
      || ['quantity', 'requestedQuantity'].some(field =>
        Object.prototype.hasOwnProperty.call(item.material || item.materialLine || {}, field))
      ? 'SupplierRecommendationDecision' : 'UNKNOWN',
    availableQuantity: item.availableQuantity === undefined ? null : number(item.availableQuantity),
    orderedQuantity,
    remainingQuantity,
    suggestedQuantity: remainingQuantity,
    suggestedPurchaseQuantity: remainingQuantity,
    originalSuggestedQuantity: remainingQuantity,
    confirmedQuantity: 0,
    itemDraftStatus: 'excluded',
    itemDraftStatusLabel: '不纳入采购订单',
    quantityConsistencyStatus: requestedQuantity > 0 ? 'pending_confirmation' : 'excluded',
    quantityConsistencyStatusLabel: requestedQuantity > 0 ? '待确认' : '不纳入采购订单',
    quantityAdjustmentReason: '',
    quantityAdjustedBy: '',
    quantityAdjustedAt: '',
    quantityAdjustmentHistory: [],
    quantity: 0,
    supplierId,
    supplierName,
    recommendedSupplierId: supplierId,
    supplierAllocationSource: 'supplier_recommendation_decision',
    quotedPrice,
    approvedPrice,
    confirmedPrice: 0,
    unitPrice: 0,
    requestedDate: text(item.requestedDate || item.requiredDate
      || item.material?.requestedDate || item.material?.requiredDate),
    supplierDeliveryDate: text(candidate.deliveryDate || item.supplierDeliveryDate),
    confirmedDeliveryDate: '',
    remark: '',
  }
}

function enrichExistingDraft(existing = {}, gate = {}) {
  const projections = (gate.recommendationItems || []).map((item, index) =>
    sourceLine(gate, item, index))
  const materialItems = (existing.materialItems || []).map((line, index) => {
    const projection = projections.find(item => item.materialCode === text(line.materialCode))
      || projections[index] || {}
    const confirmedQuantity = line.confirmedQuantity !== undefined
      && line.confirmedQuantity !== null
      ? number(line.confirmedQuantity) : number(line.quantity)
    const confirmedPrice = line.confirmedPrice !== undefined && line.confirmedPrice !== null
      && Number(line.confirmedPrice) > 0 ? number(line.confirmedPrice) : number(line.unitPrice)
    const legacyCompositeSupplier = compositeSupplierName(line.supplierName)
      || (text(line.supplierName) === text(existing.supplierName)
        && compositeSupplierName(existing.supplierName))
    const explicitSupplierId = legacyCompositeSupplier
      ? text(projection.supplierId) : text(line.supplierId || projection.supplierId)
    const explicitSupplierName = legacyCompositeSupplier
      ? text(projection.supplierName) : text(line.supplierName || projection.supplierName)
    return {
      ...projection,
      ...line,
      confirmedQuantity,
      quantity: confirmedQuantity,
      confirmedPrice,
      unitPrice: confirmedPrice,
      confirmedDeliveryDate: text(line.confirmedDeliveryDate || existing.plannedDeliveryDate),
      supplierId: explicitSupplierId,
      supplierName: explicitSupplierName,
      supplierAllocationSource: text(line.supplierAllocationSource)
        || (explicitSupplierId !== text(projection.recommendedSupplierId)
          ? 'human_confirmation' : 'supplier_recommendation_decision'),
    }
  })
  const draftStatus = existing.draftStatus || (number(existing.manualDataVersion) > 0
    ? 'confirmed' : 'editing')
  const statusLabels = { editing: '编辑中', confirmed: '已确认',
    ready_for_creation: '可创建采购订单' }
  const normalized = synchronizeSupplierPurchaseDraftsV11428427114({ ...existing,
    objectType: 'PurchaseOrderDraft',
    legacyObjectType: existing.legacyObjectType || existing.objectType || 'PurchaseOrderCreationDraft',
    supplierDataSource: 'SupplierPurchaseDraft[]',
    recommendationDecisionRole: 'evidence_only',
    draftStatus, statusLabel: statusLabels[draftStatus] || '编辑中',
    readinessStatus: existing.readinessStatus || (number(existing.manualDataVersion) > 0
      ? 'ready_for_creation' : 'editing'),
    savedToStore: existing.savedToStore ?? number(existing.manualDataVersion) > 0,
    materialItems })
  return clone({ ...normalized, ...draftSummary(normalized) })
}

export function evaluatePurchaseOrderDraftV11428427113(draft = {}) {
  const materialItems = Array.isArray(draft.materialItems) ? draft.materialItems : []
  const quantityCalculations = materialItems.map(calculatePurchaseOrderQuantityV11428427112)
  const includedItems = materialItems.filter((_line, index) =>
    quantityCalculations[index]?.itemDraftStatus === 'included')
  const excludedItems = materialItems.filter((_line, index) =>
    quantityCalculations[index]?.itemDraftStatus === 'excluded')
  const quantityReasons = quantityCalculations.flatMap(value => value.blockingReasons)
  const supplierDraftEvaluation = evaluateSupplierPurchaseDraftsV11428427114(draft)
  const missingFields = []
  if (!includedItems.length) missingFields.push('至少一个纳入采购订单的物料')
  if (includedItems.length) missingFields.push(...supplierDraftEvaluation.missingFields)
  if (!materialItems.length) missingFields.push('采购订单明细')
  const supplierDraftsById = new Map(supplierDraftEvaluation.supplierPurchaseDrafts
    .map(group => [text(group.supplierId), group]))
  materialItems.forEach((line, index) => {
    if (quantityCalculations[index]?.itemDraftStatus === 'excluded') return
    if (!text(line.supplierId) || !text(line.supplierName)) {
      missingFields.push(`第${index + 1}行确认供应商`)
    }
    if (!text(supplierDraftsById.get(text(line.supplierId))?.deliveryDate)) {
      missingFields.push(`第${index + 1}行确认交期`)
    }
  })
  const blockingReasons = [...new Set([...missingFields.map(value => `${value}未完成。`),
    ...quantityReasons])]
  return freeze({ objectType: 'PurchaseOrderDraftEvaluation',
    draftId: text(draft.draftId), totalItemCount: materialItems.length,
    includedItemCount: includedItems.length, excludedItemCount: excludedItems.length,
    completedItemCount: materialItems.filter((line, index) =>
      quantityCalculations[index]?.result === 'PASS'
      && quantityCalculations[index]?.itemDraftStatus === 'included'
      && text(line.supplierId) && text(line.supplierName)
      && text(supplierDraftsById.get(text(line.supplierId))?.deliveryDate)).length,
    supplierCount: supplierDraftEvaluation.supplierCount,
    supplierPurchaseDrafts: supplierDraftEvaluation.supplierPurchaseDrafts,
    missingFields: freeze(missingFields), quantityCalculations: freeze(quantityCalculations),
    result: blockingReasons.length ? 'BLOCKED' : 'PASS',
    blockingReasons: freeze(blockingReasons),
    readinessStatus: blockingReasons.length ? 'editing' : 'ready_for_creation' })
}

function draftSummary(draft = {}) {
  const materialItems = draft.purchaseMaterialItems || draft.materialItems || []
  const supplierPurchaseDrafts = buildSupplierPurchaseDraftsV11428427114({
    draft: { ...draft, materialItems },
  })
  const adjustmentRecords = materialItems.flatMap(line => line.quantityAdjustmentHistory || [])
  return {
    purchaseRequestIds: [...new Set(materialItems.flatMap(line => [
      ...(line.sourcePurchaseRequestIds || []), line.sourcePurchaseRequestId,
    ]).map(text).filter(Boolean))],
    confirmedSupplier: { supplierId: text(draft.supplierId),
      supplierName: text(draft.supplierName) },
    confirmedQuantity: materialItems.reduce((sum, line) =>
      sum + number(line.confirmedQuantity ?? line.quantity), 0),
    originalSuggestedQuantity: materialItems.reduce((sum, line) =>
      sum + number(line.originalSuggestedQuantity), 0),
    adjustedQuantity: materialItems.reduce((sum, line) =>
      sum + number(line.confirmedQuantity ?? line.quantity), 0),
    adjustmentRecords,
    supplierCount: supplierPurchaseDrafts.length,
    includedMaterialCount: supplierPurchaseDrafts.reduce((sum, group) =>
      sum + group.items.length, 0),
    supplierPurchaseDrafts,
    supplierDrafts: supplierPurchaseDrafts,
  }
}

function manualDraftSnapshot(draft = {}) {
  return JSON.stringify({
    supplierPurchaseDrafts: buildSupplierPurchaseDraftsV11428427114({ draft }).map(group => ({
      supplierId: group.supplierId, supplierName: group.supplierName,
      deliveryDate: group.deliveryDate, supplierRemark: group.supplierRemark,
      approvalRemark: group.approvalRemark,
    })),
    materialItems: (draft.materialItems || []).map(line => ({
      materialCode: text(line.materialCode),
      confirmedQuantity: number(line.confirmedQuantity ?? line.quantity),
      quantityAdjustmentReason: text(line.quantityAdjustmentReason),
      supplierId: text(line.supplierId), supplierName: text(line.supplierName),
      confirmedPrice: number(line.confirmedPrice ?? line.unitPrice),
      confirmedDeliveryDate: text(line.confirmedDeliveryDate),
      remark: text(line.remark),
      inventoryConfirmation: clone(line.inventoryConfirmation || null),
    })),
  })
}

export function createPurchaseOrderCreationDraftV114284262({
  gate = {}, admissionResult = {}, now = new Date().toISOString(),
} = {}) {
  const singleSupplier = (gate.recommendedSupplierIds || []).length <= 1
  const headerSupplierId = singleSupplier ? text(gate.recommendedSupplierId) : ''
  const headerSupplierName = singleSupplier ? text(gate.supplierName) : ''
  const gatePurchaseRequestIds = [...new Set([
    ...(gate.purchaseRequestIds || []), gate.purchaseRequestId,
  ].map(text).filter(Boolean))]
  return clone({
    objectType: 'PurchaseOrderDraft',
    legacyObjectType: 'PurchaseOrderCreationDraft',
    draftId: `POCD-${admissionResult.admissionResultId || gate.gateId}`,
    gateId: gate.gateId || '',
    admissionResultId: admissionResult.admissionResultId || '',
    sourceSignature: gate.sourceSignature || '',
    supplierId: headerSupplierId,
    supplierName: headerSupplierName,
    supplierDataSource: 'SupplierPurchaseDraft[]',
    recommendationDecisionRole: 'evidence_only',
    purchaseRequestIds: gatePurchaseRequestIds,
    purchaseInquiryIds: [...new Set([...(gate.inquiryIds || []), gate.inquiryId]
      .map(text).filter(Boolean))],
    quoteComparisonIds: [...new Set([...(gate.quoteComparisonIds || []), gate.quoteComparisonId]
      .map(text).filter(Boolean))],
    priceApprovalIds: [...new Set([...(gate.priceApprovalIds || []), gate.priceApprovalId]
      .map(text).filter(Boolean))],
    creationContext: {
      objectType: 'PurchaseOrderCreationContext',
      creationContextId: `POCC-${text(gate.gateId) || 'UNKNOWN'}`,
      gateId: text(gate.gateId),
      purchaseRequestIds: gatePurchaseRequestIds,
      purchaseInquiryIds: [...new Set([...(gate.inquiryIds || []), gate.inquiryId]
        .map(text).filter(Boolean))],
      quoteComparisonIds: [...new Set([...(gate.quoteComparisonIds || []), gate.quoteComparisonId]
        .map(text).filter(Boolean))],
      priceApprovalIds: [...new Set([...(gate.priceApprovalIds || []), gate.priceApprovalId]
        .map(text).filter(Boolean))],
      supplierPurchaseDrafts: [], materialItems: [],
      sourcePurchaseRequestCount: gatePurchaseRequestIds.length,
      manualDataPriority: 'HUMAN_OVER_SYSTEM_OVER_DEFAULT',
      automaticPurchaseOrderCreation: false, businessWriteCount: 0,
      productionDataWritten: false,
    },
    plannedDeliveryDate: '',
    remark: '',
    approvalOpinion: '',
    materialItems: (gate.recommendationItems || []).map((item, index) =>
      sourceLine(gate, item, index)), supplierPurchaseDrafts: [], supplierDrafts: [],
    manualDataVersion: 0,
    draftStatus: 'editing',
    statusLabel: '编辑中',
    readinessStatus: 'editing',
    savedToStore: false,
    manualDataFields: ['supplierId', 'supplierName', 'plannedDeliveryDate', 'remark',
      'approvalOpinion', 'supplierPurchaseDrafts.deliveryDate',
      'supplierPurchaseDrafts.supplierRemark', 'supplierPurchaseDrafts.approvalRemark',
      'materialItems.confirmedQuantity', 'materialItems.supplierId',
      'materialItems.supplierName', 'materialItems.confirmedPrice',
      'materialItems.confirmedDeliveryDate', 'materialItems.quantityAdjustmentReason',
      'materialItems.quantityAdjustedBy', 'materialItems.quantityAdjustedAt',
      'materialItems.remark', 'materialItems.inventoryConfirmation'],
    lastActionCode: '',
    lastModifiedBy: '',
    lastModifiedAt: '',
    createdAt: now,
    purchaseOrderCreated: false,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    productionDataWritten: false,
    ...draftSummary({ materialItems: (gate.recommendationItems || []).map((item, index) =>
      sourceLine(gate, item, index)), supplierId: headerSupplierId,
      supplierName: headerSupplierName }),
  })
}

export function createPurchaseOrderCreationDraftStoreV114284262({
  storage = browserStorage(), storageKey = PURCHASE_ORDER_CREATION_DRAFT_STORAGE_KEY_V114284262,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryDrafts)
    try {
      const values = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(values) ? values : []
    } catch { return [] }
  }
  const write = values => {
    memoryDrafts.splice(0, memoryDrafts.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
  }
  return freeze({
    findByAdmissionResultId: id => clone(read().find(item =>
      item.admissionResultId === text(id)) || null),
    resolve({ gate = {}, admissionResult = {} } = {}) {
      const existing = read().find(item => item.admissionResultId
        === text(admissionResult.admissionResultId)
        && item.gateId === text(gate.gateId)
        && item.sourceSignature === text(gate.sourceSignature))
      return existing ? enrichExistingDraft(existing, gate)
        : createPurchaseOrderCreationDraftV114284262({ gate, admissionResult })
    },
    save(draft = {}, { actionCode = '', actor = '', guard = {},
      now = new Date().toISOString() } = {}) {
      if (actionCode !== SAVE_PURCHASE_ORDER_CREATION_DRAFT_ACTION_V114284262
        || guard.result !== 'PASS' || guard.gateId !== draft.gateId
        || guard.admissionResultId !== draft.admissionResultId || !text(actor)) {
        throw new Error('PURCHASE_ORDER_CREATION_DRAFT_ACTION_GUARD_REQUIRED')
      }
      const values = read()
      const previous = values.find(item => item.draftId === draft.draftId)
      const materialItems = (draft.materialItems || []).map(line => {
        const previousLine = (previous?.materialItems || []).find(item =>
          text(item.materialCode) === text(line.materialCode))
        const confirmedQuantity = line.confirmedQuantity !== undefined
          && line.confirmedQuantity !== null
          ? number(line.confirmedQuantity) : number(line.quantity)
        const confirmedPrice = Number(line.confirmedPrice) > 0
          ? number(line.confirmedPrice) : number(line.unitPrice)
        const supplierId = text(line.supplierId)
        const supplierName = text(line.supplierName)
        const originalSuggestedQuantity = number(line.originalSuggestedQuantity
          ?? line.suggestedPurchaseQuantity ?? line.suggestedQuantity)
        const quantityChanged = confirmedQuantity !== originalSuggestedQuantity
        const quantityAdjustmentReason = text(line.quantityAdjustmentReason)
        const history = Array.isArray(line.quantityAdjustmentHistory)
          ? clone(line.quantityAdjustmentHistory) : []
        const adjustmentChanged = quantityChanged && (!previousLine
          || number(previousLine.confirmedQuantity ?? previousLine.quantity) !== confirmedQuantity
          || text(previousLine.quantityAdjustmentReason) !== quantityAdjustmentReason)
        if (adjustmentChanged) history.push({
          fromQuantity: originalSuggestedQuantity,
          toQuantity: confirmedQuantity,
          reason: quantityAdjustmentReason,
          adjustedBy: text(actor),
          adjustedAt: now,
        })
        const quantityCalculation = calculatePurchaseOrderQuantityV11428427112({
          ...line, confirmedQuantity, quantity: confirmedQuantity,
          originalSuggestedQuantity, quantityAdjustmentReason,
        })
        return { ...line, confirmedQuantity, quantity: confirmedQuantity,
          itemDraftStatus: quantityCalculation.itemDraftStatus,
          itemDraftStatusLabel: quantityCalculation.itemDraftStatusLabel,
          quantityConsistencyStatus: quantityCalculation.quantityConsistencyStatus,
          quantityConsistencyStatusLabel: quantityCalculation.quantityConsistencyStatusLabel,
          confirmedPrice, unitPrice: confirmedPrice,
          confirmedDeliveryDate: text(line.confirmedDeliveryDate || draft.plannedDeliveryDate),
          supplierId, supplierName,
          originalSuggestedQuantity,
          quantityAdjustmentReason,
          quantityAdjustedBy: adjustmentChanged
            ? text(actor) : text(line.quantityAdjustedBy),
          quantityAdjustedAt: adjustmentChanged
            ? now : text(line.quantityAdjustedAt),
          quantityAdjustmentHistory: history,
          supplierAllocationSource: supplierId !== text(line.recommendedSupplierId)
            ? 'human_confirmation' : 'supplier_recommendation_decision' }
      })
      const normalized = synchronizeSupplierPurchaseDraftsV11428427114({ ...clone(draft),
        materialItems, objectType: 'PurchaseOrderDraft',
        legacyObjectType: 'PurchaseOrderCreationDraft' })
      const materialEligibility = evaluatePurchaseOrderMaterialEligibilityV114284271144(
        normalized.materialItems)
      const effectiveDraft = { ...normalized,
        purchaseMaterialItems: materialEligibility.eligibleItems,
        recommendationEvidenceItems: materialEligibility.recommendationEvidenceItems,
        validMaterialCount: materialEligibility.validMaterialCount,
        invalidMaterialCount: materialEligibility.invalidMaterialCount }
      const evaluation = evaluatePurchaseOrderDraftV11428427113({ ...effectiveDraft,
        materialItems: materialEligibility.eligibleItems })
      const increaseWithoutReason = evaluation.quantityCalculations.some(item =>
        item.quantityIncreasedByHuman && !item.adjustmentEvidenceComplete)
      if (increaseWithoutReason) throw new Error('请输入调整原因。')
      const severeQuantityAnomaly = evaluation.quantityCalculations.some(item =>
        item.severeQuantityAnomaly)
      if (severeQuantityAnomaly) {
        throw new Error('确认采购数量超过建议采购数量10倍，请重新确认。')
      }
      const draftStatus = evaluation.result === 'PASS' ? 'confirmed' : 'editing'
      const saved = clone({ ...effectiveDraft, ...draftSummary(effectiveDraft),
        manualDataVersion: Number(previous?.manualDataVersion || 0) + 1,
        draftStatus, statusLabel: draftStatus === 'confirmed' ? '已确认' : '编辑中',
        readinessStatus: evaluation.readinessStatus, savedToStore: true,
        lastActionCode: actionCode, lastModifiedBy: text(actor), lastModifiedAt: now,
        purchaseOrderCreated: false, purchaseOrderSubmitted: false,
        purchaseOrderApproved: false, productionDataWritten: false })
      const index = values.findIndex(item => item.draftId === saved.draftId)
      if (index < 0) values.push(clone(saved)); else values.splice(index, 1, clone(saved))
      write(values)
      return saved
    },
    confirmInventory(draft = {}, { actionCode = '', actor = '', guard = {},
      materialCode = '', confirmationRemark = '', now = new Date().toISOString() } = {}) {
      if (actionCode !== CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146
        || guard.result !== 'PASS' || guard.gateId !== draft.gateId
        || guard.admissionResultId !== draft.admissionResultId || !text(actor)) {
        throw new Error('PURCHASE_ORDER_INVENTORY_CONFIRMATION_ACTION_GUARD_REQUIRED')
      }
      if (!text(confirmationRemark)) throw new Error('请填写库存人工核对备注。')
      const lineIndex = (draft.materialItems || []).findIndex(line =>
        text(line.materialCode) === text(materialCode))
      if (lineIndex < 0) throw new Error('未找到需要确认库存的物料。')
      const line = draft.materialItems[lineIndex]
      if (line.availableQuantity !== null && line.availableQuantity !== undefined
        && line.availableQuantity !== '') {
        throw new Error('当前物料库存已接入，不需要人工确认未接入库存。')
      }
      const values = read()
      const previous = values.find(item => item.draftId === draft.draftId)
      const materialItems = clone(draft.materialItems || [])
      delete materialItems[lineIndex].inventoryConfirmationEditing
      delete materialItems[lineIndex].inventoryConfirmationRemarkDraft
      materialItems[lineIndex] = { ...materialItems[lineIndex],
        inventoryConfirmation: {
          confirmed: true,
          sourceStatus: 'NOT_CONNECTED',
          confirmedBy: text(actor),
          confirmedAt: now,
          confirmationRemark: text(confirmationRemark),
          inventoryQuantityModified: false,
        } }
      const normalized = synchronizeSupplierPurchaseDraftsV11428427114({
        ...clone(draft), materialItems,
      })
      const saved = clone({ ...normalized, ...draftSummary(normalized), savedToStore: true,
        manualDataVersion: Number(previous?.manualDataVersion
          ?? draft.manualDataVersion ?? 0) + 1,
        lastActionCode: actionCode, lastModifiedBy: text(actor), lastModifiedAt: now,
        purchaseOrderCreated: false, purchaseOrderSubmitted: false,
        purchaseOrderApproved: false, productionDataWritten: false })
      const index = values.findIndex(item => item.draftId === saved.draftId)
      if (index < 0) values.push(clone(saved)); else values.splice(index, 1, clone(saved))
      write(values)
      return saved
    },
    markReadyForCreation(draft = {}, { actionCode = '', actor = '', guard = {},
      now = new Date().toISOString() } = {}) {
      if (actionCode !== CONFIRM_PURCHASE_ORDER_DRAFT_ACTION_V11428427113
        || guard.result !== 'PASS' || guard.gateId !== draft.gateId
        || guard.admissionResultId !== draft.admissionResultId || !text(actor)) {
        throw new Error('PURCHASE_ORDER_DRAFT_CONFIRM_ACTION_GUARD_REQUIRED')
      }
      const values = read()
      const persisted = values.find(item => item.draftId === draft.draftId)
      if (!persisted || number(persisted.manualDataVersion) !== number(draft.manualDataVersion)) {
        throw new Error('请先保存采购订单草稿。')
      }
      if (manualDraftSnapshot(persisted) !== manualDraftSnapshot(draft)) {
        throw new Error('草稿存在未保存修改，请先保存采购订单草稿。')
      }
      const evaluation = evaluatePurchaseOrderDraftV11428427113(draft)
      if (evaluation.result !== 'PASS') throw new Error(evaluation.blockingReasons.join('；'))
      const ready = clone({ ...draft, ...draftSummary(draft), objectType: 'PurchaseOrderDraft',
        draftStatus: 'ready_for_creation', statusLabel: '可创建采购订单',
        readinessStatus: 'ready_for_creation', savedToStore: true,
        lastActionCode: actionCode, lastModifiedBy: text(actor), lastModifiedAt: now })
      const index = values.findIndex(item => item.draftId === ready.draftId)
      values.splice(index, 1, clone(ready))
      write(values)
      return ready
    },
    clear: () => write([]),
  })
}

export const purchaseOrderCreationDraftStoreV114284262 =
  createPurchaseOrderCreationDraftStoreV114284262()
