import { executePurchaseInquiryBatchAction } from '../process/scm/purchaseInquiry/purchaseInquiryBatchActionContract.js'
import { executePurchaseInquiryAction } from './purchaseInquiryActionExecutionRuntime.js'

export const PURCHASE_INQUIRY_BATCH_RUNTIME_VERSION = 'V1.14.2.8.18.5'
const BATCH_KEY = 'pce.scm.purchase-inquiry.batch-runtime.v11428185'
let memoryBatch = null
const storage = () => typeof window !== 'undefined' ? window.sessionStorage : null

export function assessPurchaseInquiryBatchRuntime(rows = []) {
  const count = Array.isArray(rows) ? rows.length : 0
  return Object.freeze({ selectedCount: count, canBatchView: count >= 1, canBatchEdit: count >= 2,
    batchSendSupplier: false, batchCreatePurchaseOrder: false })
}

function persistBatch(context) {
  memoryBatch = context
  try { storage()?.setItem(BATCH_KEY, JSON.stringify(context)) } catch { /* memory fallback */ }
}

export function loadPurchaseInquiryBatchRuntime() {
  if (memoryBatch) return memoryBatch
  try { return JSON.parse(storage()?.getItem(BATCH_KEY) || 'null') } catch { return null }
}

export function executePurchaseInquiryBatchRuntime(rows = [], actionCode = '') {
  const capability = assessPurchaseInquiryBatchRuntime(rows)
  const operationAllowed = actionCode === 'BATCH_VIEW_PURCHASE_INQUIRIES'
    ? capability.canBatchView : actionCode === 'BATCH_EDIT_PURCHASE_INQUIRIES' && capability.canBatchEdit
  if (!operationAllowed) return Object.freeze({ result: 'FAIL', allowed: false, capability })
  const contract = executePurchaseInquiryBatchAction(rows, actionCode)
  if (!contract.valid) return Object.freeze({ result: 'FAIL', allowed: false, capability, contract })
  const itemAction = actionCode === 'BATCH_VIEW_PURCHASE_INQUIRIES' ? 'VIEW_PURCHASE_INQUIRY' : 'EDIT_PURCHASE_INQUIRY'
  const firstExecution = executePurchaseInquiryAction({ inquiry: rows[0], actionCode: itemAction })
  const route = actionCode === 'BATCH_VIEW_PURCHASE_INQUIRIES'
    ? '/scm/purchase-inquiry/acceptance/batch?mode=view' : firstExecution.route
  const context = Object.freeze({ runtimeCode: 'SCM_PURCHASE_INQUIRY_BATCH_RUNTIME', actionCode,
    inquiries: Object.freeze([...rows]), selectedCount: rows.length, currentIndex: 0, route,
    supplierSent: false, purchaseOrderCreated: false, productionDataWritten: false })
  persistBatch(context)
  return Object.freeze({ result: 'PASS', allowed: true, route, capability, contract, context })
}

export function advancePurchaseInquiryBatchRuntime() {
  const batch = loadPurchaseInquiryBatchRuntime()
  if (!batch || batch.actionCode !== 'BATCH_EDIT_PURCHASE_INQUIRIES') return Object.freeze({ complete: true })
  const nextIndex = batch.currentIndex + 1
  if (nextIndex >= batch.inquiries.length) return Object.freeze({ complete: true })
  const execution = executePurchaseInquiryAction({ inquiry: batch.inquiries[nextIndex], actionCode: 'EDIT_PURCHASE_INQUIRY' })
  const next = Object.freeze({ ...batch, currentIndex: nextIndex, route: execution.route })
  persistBatch(next)
  return Object.freeze({ complete: false, route: execution.route, inquiry: batch.inquiries[nextIndex] })
}
