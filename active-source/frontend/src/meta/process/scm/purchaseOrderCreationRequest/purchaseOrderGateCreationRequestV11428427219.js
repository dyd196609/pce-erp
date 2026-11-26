export const PURCHASE_ORDER_GATE_CREATION_REQUEST_VERSION_V11428427219 =
  'V1.14.2.8.4.27.2.19'

const STORAGE_KEY = 'pce.scm.purchase-order.gate-creation-requests.v11428427219'
const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(clone(value))

function readAll() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value : []
  } catch { return [] }
}

function saveAll(rows) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rows))
  return rows
}

function materialLines(gate = {}, sourceLines = []) {
  return (gate.recommendationItems || []).map((item, index) => {
    const sourceLine = sourceLines.find(line => text(line.materialCode) === text(item.materialCode)) || {}
    return ({
    lineNo: index + 1,
    sourceRequestNo: text(sourceLine.sourceRequestNo || sourceLine.requestNo),
    sourcePurchaseRequestItemId: text(sourceLine.purchaseRequestItemId || sourceLine.id),
    materialCode: text(item.materialCode || item.material?.materialCode),
    materialName: text(item.materialName || item.material?.materialName || `采购物料${index + 1}`),
    specification: text(item.specification || item.material?.specification),
    quantity: Number(sourceLine.quantity
      || item.confirmedQuantity || item.quantity || item.requestedQuantity || 0),
    unitPrice: Number(item.approvedPrice || item.selectedPrice || item.quotePrice || item.price || 0),
    expectedDate: text(item.requiredDate || item.deliveryDate || sourceLine.requiredDate
      || sourceLine.expectedDate),
    priceApprovalId: text(item.priceApprovalId || item.sourcePriceApprovalId),
    priceApprovalIds: [...new Set([
      ...(item.priceApprovalIds || []), ...(item.sourcePriceApprovalIds || []),
      item.priceApprovalId, item.sourcePriceApprovalId,
    ].map(text).filter(Boolean))],
    priceApprovalNo: text(item.priceApprovalNo || item.sourcePriceApprovalPreparationNo),
    priceApprovalNos: [...new Set([
      ...(item.priceApprovalNos || []), item.priceApprovalNo,
      item.sourcePriceApprovalPreparationNo,
    ].map(text).filter(Boolean))],
    priceApprovalResultId: text(item.priceApprovalResultId),
    priceApprovalResultNo: text(item.priceApprovalResultNo),
    quoteComparisonId: text(item.quoteComparisonId || item.sourceQuoteComparisonId
      || item.quoteComparisonIds?.[0]),
    quoteComparisonIds: [...new Set([
      ...(item.quoteComparisonIds || []), ...(item.sourceQuoteComparisonIds || []),
      item.quoteComparisonId, item.sourceQuoteComparisonId,
    ].map(text).filter(Boolean))],
    selectedSupplierCode: text(item.selectedSupplierCode || item.decisionSupplier?.supplierCode),
    selectedSupplierName: text(item.selectedSupplierName || item.decisionSupplier?.supplierName),
    supplierCandidates: (item.supplierCandidates || []).map(candidate => ({
      supplierCode: text(candidate.supplierCode || candidate.code),
      supplierName: text(candidate.supplierName || candidate.name),
    })).filter(candidate => candidate.supplierCode && candidate.supplierName),
    })
  })
}

function supplierGroups(gate = {}, lines = []) {
  const groups = new Map()
  const topCandidates = (gate.supplierCandidates || []).map(candidate => ({
    supplierCode: text(candidate.supplierCode || candidate.code),
    supplierName: text(candidate.supplierName || candidate.name),
  })).filter(candidate => candidate.supplierCode && candidate.supplierName)
  const append = (candidate, line) => {
    const code = text(candidate.supplierCode)
    const name = text(candidate.supplierName)
    if (!code || !name) return
    const group = groups.get(code) || { supplierCode: code, supplierName: name, materialLines: [] }
    if (!group.materialLines.some(value => value.materialCode === line.materialCode)) {
      group.materialLines.push({ ...line, supplierCandidates: undefined })
    }
    groups.set(code, group)
  }
  for (const line of lines) {
    const candidates = topCandidates.length ? topCandidates : line.supplierCandidates.length
      ? line.supplierCandidates : [{ supplierCode: line.selectedSupplierCode,
        supplierName: line.selectedSupplierName }]
    candidates.forEach(candidate => append(candidate, line))
  }
  return [...groups.values()]
}

export function createPurchaseOrderGateCreationRequestV11428427219({
  gate = {}, admissionResult = {}, creationEntry = {}, actor = {}, sourceMaterialLines = [],
  now = new Date().toISOString(),
} = {}) {
  if (gate.objectType !== 'SupplierRecommendationGate'
    || gate.status !== 'READY_FOR_PURCHASE_ORDER'
    || gate.purchaseOrderCreationAllowed !== true
    || admissionResult.objectType !== 'PurchaseOrderAdmissionResult'
    || admissionResult.status !== 'READY_FOR_PURCHASE_ORDER'
    || creationEntry.objectType !== 'PurchaseOrderCreationEntry') {
    throw new Error('PURCHASE_ORDER_GATE_READY_FACTS_REQUIRED')
  }
  const lines = materialLines(gate, sourceMaterialLines)
  if (!lines.length || lines.some(line => !line.materialCode || !(line.quantity > 0))) {
    throw new Error('PURCHASE_ORDER_SOURCE_MATERIAL_QUANTITY_REQUIRED')
  }
  const groups = supplierGroups(gate, lines)
  if (!groups.length || groups.some(group => !group.materialLines.length)) {
    throw new Error('PURCHASE_ORDER_SUPPLIER_SPLIT_FACTS_REQUIRED')
  }
  const requestId = `POCR-${text(gate.gateId)}-${Date.now()}`
  return freeze({
    objectType: 'PurchaseOrderCreationRequest', requestId,
    gateId: text(gate.gateId), admissionResultId: text(admissionResult.admissionResultId),
    creationEntryId: text(creationEntry.entryId), sourceSignature: text(gate.sourceSignature),
    sourceObjectType: gate.objectType, sourceObjectId: text(gate.gateId),
    purchaseRequestIds: gate.purchaseRequestIds || [], inquiryIds: gate.inquiryIds || [],
    quoteComparisonIds: gate.quoteComparisonIds || [], priceApprovalIds: gate.priceApprovalIds || [],
    recommendedSupplierCode: text(gate.recommendedSupplierId),
    recommendedSupplierName: text(gate.supplierName),
    supplierGroups: groups, supplierCount: groups.length,
    materialLines: lines, status: 'PENDING_CONFIRMATION',
    statusLabel: '等待人工确认创建采购订单', createdBy: text(actor.userName || actor.userId || actor.role),
    createdAt: now, confirmedBy: '', confirmedAt: '', purchaseOrderCreated: false,
  })
}

export const purchaseOrderGateCreationRequestStoreV11428427219 = Object.freeze({
  save(request) {
    const rows = readAll()
    const existing = rows.find(row => row.requestId === request.requestId)
    if (existing) return freeze(existing)
    saveAll([clone(request), ...rows])
    return freeze(request)
  },
  find(requestId) {
    const row = readAll().find(item => item.requestId === requestId)
    return row ? freeze(row) : null
  },
  markCreated(requestId, purchaseOrder, actor = {}, now = new Date().toISOString()) {
    const rows = readAll()
    const index = rows.findIndex(item => item.requestId === requestId)
    if (index < 0) throw new Error('PURCHASE_ORDER_CREATION_REQUEST_NOT_FOUND')
    rows[index] = { ...rows[index], status: 'COMPLETED', statusLabel: '采购订单已创建',
      confirmedBy: text(actor.userName || actor.userId || actor.role), confirmedAt: now,
      purchaseOrderCreated: true,
      purchaseOrderObjectIds: purchaseOrder.purchaseOrders?.map(item => item.objectId)
        || [purchaseOrder.objectId].filter(Boolean),
      purchaseOrderObjectNos: purchaseOrder.purchaseOrders?.map(item => item.objectNo)
        || [purchaseOrder.objectNo].filter(Boolean),
      purchaseOrderObjectId: purchaseOrder.objectId,
      purchaseOrderObjectNo: purchaseOrder.objectNo }
    saveAll(rows)
    return freeze(rows[index])
  },
  count() { return readAll().length },
})
