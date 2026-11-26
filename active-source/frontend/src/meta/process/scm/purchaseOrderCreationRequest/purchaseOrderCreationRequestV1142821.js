import { canPerformAction } from '../../../runtime/permissionEngine.js'

export const PURCHASE_ORDER_CREATION_REQUEST_VERSION_V1142821 = 'V1.14.2.8.18.21'
export const PURCHASE_ORDER_CREATION_REQUEST_STORAGE_KEY_V1142821 =
  'pce.scm.purchase-order-creation-request.v1142821'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryRequests = []

const requestTransitions = freeze({
  created: freeze(['reviewing', 'cancelled']),
  reviewing: freeze(['approved_for_creation', 'cancelled']),
  approved_for_creation: freeze(['cancelled']),
  cancelled: freeze([]),
})

const selectedCandidate = item => (item.supplierCandidates || []).find(candidate =>
  text(candidate.supplierCode) === text(item.selectedSupplierCode
    || item.decisionSupplier?.supplierCode)) || item.decisionSupplier || null

const selectedEvidence = item => (item.priceEvidence || []).filter(evidence => {
  const code = text(evidence.supplierCode)
  return !code || code === text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode)
})

const numericFact = (...values) => {
  const value = values.find(candidate => candidate !== '' && candidate != null
    && Number.isFinite(Number(candidate)))
  return value == null ? null : Number(value)
}

const projectMaterialItem = item => {
  const candidate = selectedCandidate(item)
  const evidence = selectedEvidence(item)
  const quantity = numericFact(item.quantity, item.requestedQuantity, candidate?.quantity,
    candidate?.quoteQuantity, evidence.find(value => value.quantity != null)?.quantity)
  const unitPrice = numericFact(candidate?.quotePrice, candidate?.unitPrice,
    evidence.find(value => value.currentPrice != null)?.currentPrice)
  return freeze({
    decisionItemId: text(item.decisionItemId),
    materialCode: text(item.materialCode),
    materialName: text(item.materialName),
    quantity: quantity ?? 0,
    quantityFactPresent: quantity != null,
    unitPrice: unitPrice ?? 0,
    amount: quantity != null && unitPrice != null
      ? Number((quantity * unitPrice).toFixed(2)) : 0,
    quoteComparisonIds: frozen(item.quoteComparisonIds || []),
    sourcePriceApprovalIds: frozen(item.sourcePriceApprovalIds || []),
    recommendationReason: text(item.selectionReason || item.decisionReason),
    manualConfirmedBy: text(item.reviewer),
    manualConfirmedAt: text(item.reviewedAt),
    quoteComparisonEvidence: frozen(evidence.filter(value =>
      /QuoteComparison/i.test(text(value.evidenceSource)) || value.currentPrice != null)),
    historicalPriceEvidence: frozen(evidence.filter(value => value.historyPrice != null
      || value.historicalPurchasePrice != null || value.priceReferenceContext
      || /PurchaseOrderHistory|PriceReference/i.test(text(value.evidenceSource)))),
  })
}

export function createPurchaseOrderCreationRequestsV1142821({
  decisionBatchResult = {}, gateDecision = {}, purchaseContext = {}, createdBy = '',
  now = new Date().toISOString(),
} = {}) {
  if (decisionBatchResult.objectType !== 'SupplierRecommendationDecisionBatchResult'
    || decisionBatchResult.status !== 'confirmed' || !text(decisionBatchResult.batchId)
    || !Array.isArray(decisionBatchResult.items) || !decisionBatchResult.items.length) {
    throw new Error('CONFIRMED_DECISION_BATCH_RESULT_REQUIRED')
  }
  if (gateDecision.objectType !== 'PurchaseOrderCreationGateDecision'
    || gateDecision.status !== 'ready_for_purchase_order'
    || gateDecision.sourceBatchId !== decisionBatchResult.batchId
    || gateDecision.sourceResultStatus !== 'confirmed'
    || gateDecision.batchCompleteness?.pendingItemCount !== 0
    || !gateDecision.purchaseOrderCreationAllowed) {
    throw new Error('PURCHASE_ORDER_GATE_READY_REQUIRED')
  }
  if (Number(gateDecision.sourceDecisionRevision) !== Number(decisionBatchResult.decisionRevision)) {
    throw new Error('GATE_DECISION_REVISION_MISMATCH')
  }
  const groups = new Map()
  for (const item of decisionBatchResult.items) {
    const supplierCode = text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode)
    const supplierName = text(item.selectedSupplierName || item.decisionSupplier?.supplierName)
    if (!supplierCode || !supplierName || item.reviewStatus !== 'confirmed'
      || !text(item.selectionReason || item.decisionReason) || !text(item.reviewer)
      || !text(item.reviewedAt)) throw new Error('DECISION_BATCH_ITEM_INCOMPLETE')
    const current = groups.get(supplierCode) || { supplierCode, supplierName, items: [] }
    current.items.push(projectMaterialItem(item))
    groups.set(supplierCode, current)
  }
  return freeze([...groups.values()].map(group => {
    const materialItems = frozen(group.items)
    return freeze({
      objectType: 'PurchaseOrderCreationRequest',
      requestId: `POCR-${decisionBatchResult.batchId}-R${Number(decisionBatchResult.decisionRevision)}-${group.supplierCode}`,
      sourceDecisionBatchId: decisionBatchResult.batchId,
      sourceDecisionRevision: Number(decisionBatchResult.decisionRevision),
      sourceObjectType: 'SupplierRecommendationDecisionBatchResult',
      sourceTrace: freeze({
        factSource: 'SupplierRecommendationDecisionBatchResult',
        decisionBatchResultId: `SRDBR-${decisionBatchResult.batchId}-R${Number(decisionBatchResult.decisionRevision)}`,
        gateId: gateDecision.gateDecisionId,
        gateStatus: gateDecision.status,
        sourceDecisionSignature: gateDecision.sourceDecisionSignature,
        historicalPurchaseOrderReadCount: 0,
      }),
      purchaseContext: frozen(purchaseContext),
      supplierCode: group.supplierCode,
      supplierName: group.supplierName,
      materialItems,
      totalAmount: Number(materialItems.reduce((sum, item) => sum + item.amount, 0).toFixed(2)),
      requestStatus: 'created',
      createdBy: text(createdBy),
      createdAt: now,
      updatedBy: text(createdBy),
      updatedAt: now,
      purchaseOrderCreated: false,
      purchaseOrderSubmitted: false,
      purchaseOrderApproved: false,
      downstreamWriteCount: 0,
    })
  }))
}

export function transitionPurchaseOrderCreationRequestV1142821(request = {}, nextStatus = '', {
  permissionContext = {}, now = new Date().toISOString(),
} = {}) {
  if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
    throw new Error('ACTION_PERMISSION_DENIED')
  }
  const target = text(nextStatus)
  if (!requestTransitions[request.requestStatus]?.includes(target)) {
    throw new Error('PURCHASE_ORDER_CREATION_REQUEST_TRANSITION_NOT_ALLOWED')
  }
  return freeze({ ...frozen(request), requestStatus: target,
    updatedBy: text(permissionContext.userName || permissionContext.user?.name
      || permissionContext.userId || permissionContext.role), updatedAt: now,
    purchaseOrderCreated: false, purchaseOrderSubmitted: false,
    purchaseOrderApproved: false, downstreamWriteCount: 0 })
}

export function createPurchaseOrderCreationRequestStoreV1142821({
  storage = browserStorage(), storageKey = PURCHASE_ORDER_CREATION_REQUEST_STORAGE_KEY_V1142821,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryRequests)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryRequests.splice(0, memoryRequests.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    list: () => frozen(read()),
    listByBatchId: batchId => frozen(read().filter(item =>
      item.sourceDecisionBatchId === text(batchId))),
    findById: requestId => frozen(read().find(item => item.requestId === text(requestId)) || null),
    saveAll(requests = []) {
      const values = read()
      for (const request of requests) {
        if (request.objectType !== 'PurchaseOrderCreationRequest'
          || request.purchaseOrderCreated !== false) throw new Error('CREATION_REQUEST_NOT_SAVABLE')
        const index = values.findIndex(item => item.requestId === request.requestId)
        if (index < 0) values.push(clone(request)); else values.splice(index, 1, clone(request))
      }
      write(values)
      return frozen(requests)
    },
    save(request) { return this.saveAll([request])[0] },
    clear: () => write([]),
  })
}

export const purchaseOrderCreationRequestStoreV1142821 =
  createPurchaseOrderCreationRequestStoreV1142821()
