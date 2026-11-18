import { canPerformAction } from '../../../runtime/permissionEngine.js'
import { applyPurchaseOrderAdmissionResultV11428425,
  confirmSupplierRecommendationGateV11428425,
  createPurchaseOrderAdmissionContextV11428425,
  createPurchaseOrderAdmissionResultV11428425 } from '../../../domain/scm/purchaseOrder/gate/supplierRecommendationGateV11428425.js'
import { evaluatePurchaseOrderAdmissionGuardV11428425 } from '../../../domain/scm/purchaseOrder/gate/purchaseOrderAdmissionGuardV11428425.js'

export const CONFIRM_PURCHASE_ORDER_GATE_ACTION_VERSION_V11428425 = 'V1.14.2.8.4.25'
export const SUPPLIER_RECOMMENDATION_GATE_STORAGE_KEY_V11428425 =
  'pce.scm.supplier-recommendation-gate.runtime.v11428425'
export const PURCHASE_ORDER_ADMISSION_RESULT_STORAGE_KEY_V11428425 =
  'pce.scm.purchase-order-admission-result.runtime.v11428425'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryGates = []
const memoryAdmissionResults = []

export function createSupplierRecommendationGateStoreV11428425({
  storage = browserStorage(), storageKey = SUPPLIER_RECOMMENDATION_GATE_STORAGE_KEY_V11428425,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryGates)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryGates.splice(0, memoryGates.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    list: read,
    findBySourceBatchId: batchId => [...read()].reverse()
      .find(item => item.sourceDecisionBatchId === text(batchId)) || null,
    save(gate) {
      if (gate.objectType !== 'SupplierRecommendationGate'
        || !['CONFIRMED', 'READY_FOR_PURCHASE_ORDER', 'BLOCKED'].includes(gate.status)
        || gate.purchaseOrderCreated !== false) {
        throw new Error('SUPPLIER_RECOMMENDATION_GATE_NOT_SAVABLE')
      }
      const values = read()
      const index = values.findIndex(item => item.gateId === gate.gateId)
      if (index < 0) values.push(clone(gate)); else values.splice(index, 1, clone(gate))
      return freeze(write(values).find(item => item.gateId === gate.gateId))
    },
    clear: () => write([]),
  })
}

export const supplierRecommendationGateStoreV11428425 =
  createSupplierRecommendationGateStoreV11428425()

export function createPurchaseOrderAdmissionResultStoreV11428425({
  storage = browserStorage(), storageKey = PURCHASE_ORDER_ADMISSION_RESULT_STORAGE_KEY_V11428425,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryAdmissionResults)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryAdmissionResults.splice(0, memoryAdmissionResults.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    list: read,
    findByGateId: gateId => [...read()].reverse()
      .find(item => item.gateId === text(gateId)) || null,
    save(result) {
      if (result.objectType !== 'PurchaseOrderAdmissionResult'
        || !['READY_FOR_PURCHASE_ORDER', 'BLOCKED'].includes(result.status)
        || result.purchaseOrderCreated !== false) {
        throw new Error('PURCHASE_ORDER_ADMISSION_RESULT_NOT_SAVABLE')
      }
      const values = read()
      values.push(clone(result))
      return freeze(write(values).at(-1))
    },
    clear: () => write([]),
  })
}

export const purchaseOrderAdmissionResultStoreV11428425 =
  createPurchaseOrderAdmissionResultStoreV11428425()

export function executeConfirmPurchaseOrderGateV11428425(gate = {}, input = {}, {
  store = supplierRecommendationGateStoreV11428425,
  permissionContext = {}, now = new Date().toISOString(),
} = {}) {
  if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
    return freeze({ result: 'FAIL', error: 'ACTION_PERMISSION_DENIED',
      businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
  }
  const confirmedBy = text(input.confirmedBy || permissionContext.userName
    || permissionContext.user?.name || permissionContext.userId || permissionContext.role)
  if (!confirmedBy) return freeze({ result: 'FAIL', error: 'GATE_CONFIRMER_REQUIRED',
    businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
  try {
    const confirmedGate = store.save(confirmSupplierRecommendationGateV11428425(gate,
      { confirmedBy, confirmedAt: now }))
    return freeze({ result: 'PASS', actionCode: 'CONFIRM_PURCHASE_ORDER_GATE',
      gate: confirmedGate, businessWriteCount: 1, productionDataWritten: false,
      purchaseOrderCreated: false, purchaseOrderCreationActionTriggered: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, businessWriteCount: 0,
      productionDataWritten: false, purchaseOrderCreated: false })
  }
}

export function executeEvaluatePurchaseOrderAdmissionV11428425(gate = {}, {
  checkedBy = '',
} = {}, {
  gateStore = supplierRecommendationGateStoreV11428425,
  resultStore = purchaseOrderAdmissionResultStoreV11428425,
  decisionBatchResult = {}, permissionContext = {}, now = new Date().toISOString(),
} = {}) {
  if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
    return freeze({ result: 'FAIL', error: 'ACTION_PERMISSION_DENIED',
      businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
  }
  const checker = text(checkedBy || permissionContext.userName || permissionContext.user?.name
    || permissionContext.userId || permissionContext.role)
  if (!checker) return freeze({ result: 'FAIL', error: 'ADMISSION_CHECKER_REQUIRED',
    businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
  try {
    const context = createPurchaseOrderAdmissionContextV11428425(gate, now)
    const guard = evaluatePurchaseOrderAdmissionGuardV11428425({ gate,
      decisionBatchResult, checkedBy: checker })
    const admissionResult = resultStore.save(
      createPurchaseOrderAdmissionResultV11428425(context, gate, guard, now))
    const updatedGate = gateStore.save(applyPurchaseOrderAdmissionResultV11428425(gate,
      admissionResult))
    return freeze({ result: 'PASS', actionCode: 'EVALUATE_PURCHASE_ORDER_ADMISSION',
      context, guard, admissionResult, gate: updatedGate,
      businessWriteCount: 2, productionDataWritten: false, purchaseOrderCreated: false,
      purchaseOrderCreationActionTriggered: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, businessWriteCount: 0,
      productionDataWritten: false, purchaseOrderCreated: false })
  }
}
