export const PURCHASE_ORDER_GATE_INSPECTION_RECORD_VERSION_V11428202 = 'V1.14.2.8.18.20.2'
export const PURCHASE_ORDER_GATE_INSPECTION_REVISION_VERSION_V11428203 = 'V1.14.2.8.18.20.3'
export const PURCHASE_ORDER_GATE_INSPECTION_RECORD_STORAGE_KEY_V11428202 =
  'pce.scm.purchase-order-gate.inspection-record.v11428202'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryRecords = []

export function createPurchaseOrderGateInspectionRecordV11428202(decision = {}, sequence = 1) {
  if (decision.objectType !== 'PurchaseOrderCreationGateDecision'
    || !text(decision.gateDecisionId) || !['ready_for_purchase_order', 'blocked'].includes(decision.status)
    || !text(decision.checkedBy) || !text(decision.lastCheckedAt)) {
    throw new Error('PURCHASE_ORDER_GATE_INSPECTION_DECISION_REQUIRED')
  }
  const checkResult = decision.status === 'ready_for_purchase_order' ? 'PASS' : 'FAIL'
  return freeze({
    objectType: 'PurchaseOrderGateInspectionRecord',
    inspectionId: `${decision.gateDecisionId}-INS-${String(sequence).padStart(3, '0')}`,
    gateId: decision.gateDecisionId,
    sourceBatchId: decision.sourceBatchId,
    decisionRevision: decision.sourceDecisionRevision,
    supplierSnapshot: frozen((decision.items || []).map(item => ({
      materialCode: item.materialCode,
      supplierCode: item.selectedSupplierCode,
      supplierName: item.selectedSupplierName,
    }))),
    checker: decision.checkedBy,
    checkedAt: decision.lastCheckedAt,
    checkResult,
    checkItems: frozen((decision.checks || []).map(item => ({
      checkCode: item.checkCode,
      checkName: item.checkName,
      result: item.result,
      blockedReason: item.blockedReason || '',
    }))),
    blockReasons: frozen(decision.blockedReasons || []),
    confirmationAction: 'SupplierRecommendationDecisionBatch confirmed',
    inspectionAction: 'Evaluate PurchaseOrder Gate',
    purchaseOrderCreated: false,
  })
}

export function createPurchaseOrderGateInspectionRecordStoreV11428202({
  storage = browserStorage(), storageKey = PURCHASE_ORDER_GATE_INSPECTION_RECORD_STORAGE_KEY_V11428202,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryRecords)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryRecords.splice(0, memoryRecords.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    list: () => read(),
    listByGateId: gateId => read().filter(item => item.gateId === text(gateId)),
    listByBatchId: batchId => read().filter(item => item.sourceBatchId === text(batchId)),
    save(record) {
      if (record.objectType !== 'PurchaseOrderGateInspectionRecord'
        || record.purchaseOrderCreated !== false) {
        throw new Error('PURCHASE_ORDER_GATE_INSPECTION_RECORD_NOT_SAVABLE')
      }
      const values = read()
      if (values.some(item => item.inspectionId === record.inspectionId)) {
        throw new Error('PURCHASE_ORDER_GATE_INSPECTION_RECORD_DUPLICATE')
      }
      values.push(clone(record))
      return frozen(write(values).find(item => item.inspectionId === record.inspectionId))
    },
    clear: () => write([]),
  })
}

export const purchaseOrderGateInspectionRecordStoreV11428202 =
  createPurchaseOrderGateInspectionRecordStoreV11428202()
