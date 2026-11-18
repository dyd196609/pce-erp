import { evaluatePurchaseOrderSourceReference } from './purchaseOrderSourceReference.js'

export const PURCHASE_ORDER_CREATION_CONTEXT_VERSION = 'V1.14.2.8.5.6'
export const PURCHASE_ORDER_CREATION_CONTEXT_CODE = 'SCM_PURCHASE_ORDER_CREATION_CONTEXT'
export const PURCHASE_ORDER_CREATION_CONTEXT_VERSION_V114284271145 =
  'V1.14.2.8.4.27.1.4.5'

const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))
const unique = values => [...new Set(values.flat(Infinity).map(text).filter(Boolean))]
const requestIdentity = value => unique([
  value?.id, value?.requestId, value?.requestNo, value?.request_no,
])
const requestLines = value => value?.materialItems || value?.materials
  || value?.lines || value?.items || []

function lineMaterialCode(line = {}) {
  return text(line.materialCode || line.code || line.material?.materialCode)
}

function lineRequestedQuantity(line = {}) {
  return number(line.requestedQuantity ?? line.quantity ?? line.material?.quantity)
}

function mergePurchaseRequestMaterialItems({ purchaseRequestIds = [], purchaseRequestFacts = [],
  purchaseRequests = [], purchaseRequestItems = [], draftItems = [] } = {}) {
  const requestedIds = new Set(purchaseRequestIds.map(text))
  const sourceRows = []

  purchaseRequestIds.forEach(purchaseRequestId => {
    const serverRequest = purchaseRequestFacts.find(value =>
      requestIdentity(value).includes(text(purchaseRequestId)))
    const runtimeRequest = purchaseRequests.find(value =>
      requestIdentity(value).includes(text(purchaseRequestId)))
    const runtimeRequestIds = new Set(unique([purchaseRequestId, requestIdentity(runtimeRequest)]))
    const serverLines = requestLines(serverRequest)
    const runtimeLines = purchaseRequestItems.filter(value =>
      runtimeRequestIds.has(text(value.requestId || value.sourcePurchaseRequestId)))
    const lines = serverLines.length ? serverLines : runtimeLines
    lines.forEach(line => sourceRows.push({ ...line,
      sourcePurchaseRequestId: text(purchaseRequestId),
      sourcePurchaseRequestIds: [text(purchaseRequestId)],
      quantitySource: serverLines.length ? 'PurchaseRequestServerFact' : 'PurchaseRequestItem',
    }))
  })

  const grouped = new Map()
  sourceRows.forEach(line => {
    const materialCode = lineMaterialCode(line)
    if (!materialCode) return
    const current = grouped.get(materialCode) || { materialCode,
      materialName: text(line.materialName || line.name || line.material?.materialName),
      materialId: text(line.materialId || line.id || line.material?.materialId),
      requestedQuantity: 0, sourcePurchaseRequestIds: [], sourceLines: [] }
    current.requestedQuantity += lineRequestedQuantity(line)
    current.sourcePurchaseRequestIds = unique([
      current.sourcePurchaseRequestIds, line.sourcePurchaseRequestIds,
      line.sourcePurchaseRequestId,
    ])
    current.sourceLines.push({ sourcePurchaseRequestId: line.sourcePurchaseRequestId,
      requestedQuantity: lineRequestedQuantity(line) })
    if (!current.materialName) current.materialName = text(line.materialName || line.name)
    if (!current.materialId) current.materialId = text(line.materialId || line.id)
    current.quantitySource = line.quantitySource
    grouped.set(materialCode, current)
  })

  const existingByMaterial = new Map(draftItems.map(line => [lineMaterialCode(line), line]))
  const merged = [...grouped.values()].map((source, index) => {
    const existing = existingByMaterial.get(source.materialCode) || {}
    existingByMaterial.delete(source.materialCode)
    const sourcePurchaseRequestIds = unique([
      source.sourcePurchaseRequestIds, existing.sourcePurchaseRequestIds,
      existing.sourceRequestIds, existing.sourcePurchaseRequestId,
    ]).filter(value => requestedIds.has(value))
    return { ...source, ...existing, lineNo: existing.lineNo || index + 1,
      materialCode: source.materialCode,
      materialName: text(existing.materialName || source.materialName),
      materialId: text(existing.materialId || source.materialId),
      requestedQuantity: source.requestedQuantity,
      sourcePurchaseRequestIds,
      sourcePurchaseRequestId: sourcePurchaseRequestIds[0] || '',
      purchaseRequestMergeType: sourcePurchaseRequestIds.length > 1 ? 'MERGED_FROM' : 'SOURCE_FROM',
      quantitySource: source.quantitySource,
      sourceLines: source.sourceLines,
    }
  })

  existingByMaterial.forEach(existing => {
    const sourcePurchaseRequestIds = unique([
      existing.sourcePurchaseRequestIds, existing.sourceRequestIds,
      existing.sourcePurchaseRequestId,
    ]).filter(value => !requestedIds.size || requestedIds.has(value))
    merged.push({ ...existing, sourcePurchaseRequestIds,
      sourcePurchaseRequestId: sourcePurchaseRequestIds[0] || '',
      purchaseRequestMergeType: sourcePurchaseRequestIds.length > 1 ? 'MERGED_FROM' : 'SOURCE_FROM',
    })
  })
  return merged
}

export function buildPurchaseOrderCreationContextV114284271145({ gate = {}, draft = {},
  purchaseRequestFacts = [], scmState = {} } = {}) {
  const draftItems = Array.isArray(draft.materialItems) ? draft.materialItems : []
  const purchaseRequestIds = unique([
    gate.purchaseRequestIds, gate.purchaseRequestId, draft.purchaseRequestIds,
    draft.creationContext?.purchaseRequestIds,
    draftItems.flatMap(line => [line.sourcePurchaseRequestIds,
      line.sourceRequestIds, line.sourcePurchaseRequestId]),
  ])
  const materialItems = mergePurchaseRequestMaterialItems({ purchaseRequestIds,
    purchaseRequestFacts, purchaseRequests: scmState.purchaseRequests || [],
    purchaseRequestItems: scmState.purchaseRequestItems || [], draftItems })
  const context = {
    objectType: 'PurchaseOrderCreationContext',
    version: PURCHASE_ORDER_CREATION_CONTEXT_VERSION_V114284271145,
    gateId: text(gate.gateId || draft.gateId),
    creationContextId: `POCC-${text(gate.gateId || draft.gateId) || 'UNKNOWN'}`,
    purchaseRequestIds,
    purchaseInquiryIds: unique([gate.inquiryIds, gate.inquiryId,
      draft.purchaseInquiryIds, draft.creationContext?.purchaseInquiryIds]),
    quoteComparisonIds: unique([gate.quoteComparisonIds, gate.quoteComparisonId,
      draft.quoteComparisonIds, draft.creationContext?.quoteComparisonIds]),
    priceApprovalIds: unique([gate.priceApprovalIds, gate.priceApprovalId,
      draft.priceApprovalIds, draft.creationContext?.priceApprovalIds]),
    supplierPurchaseDrafts: clone(draft.supplierPurchaseDrafts || []),
    materialItems: clone(materialItems),
    sourcePurchaseRequestCount: purchaseRequestIds.length,
    materialMergePolicy: 'MATERIAL_CODE_WITH_SOURCE_PURCHASE_REQUEST_IDS',
    manualDataPriority: 'HUMAN_OVER_SYSTEM_OVER_DEFAULT',
    automaticPurchaseOrderCreation: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  }
  return Object.freeze(clone(context))
}

export function buildPurchaseOrderCreationContext(input = {}) {
  const sourceEvaluation = evaluatePurchaseOrderSourceReference({ sourceObject: input.sourceObject, sourceReferenceId: input.sourceReferenceId })
  const gateEligible = input.gateEligibilityResult === 'ELIGIBLE'
  const ready = sourceEvaluation.result === 'PASS' && gateEligible
  return Object.freeze({
    contextCode: PURCHASE_ORDER_CREATION_CONTEXT_CODE,
    contextStatus: ready ? 'READY' : 'BLOCKED',
    sourceObject: input.sourceObject || '',
    sourceReferenceId: input.sourceReferenceId || '',
    supplierId: input.supplierId || '',
    gateEligibilityResult: input.gateEligibilityResult || 'UNKNOWN',
    evidenceReferences: Object.freeze(Array.isArray(input.evidenceReferences) ? [...input.evidenceReferences] : []),
    blockingReasons: Object.freeze([
      ...(sourceEvaluation.result === 'PASS' ? [] : [sourceEvaluation.reason]),
      ...(gateEligible ? [] : ['purchase_order_creation_gate_not_eligible']),
    ]),
    sourceEvaluation,
    readOnly: true,
    createsPurchaseOrder: false,
    createsBusinessTransaction: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
