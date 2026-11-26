import { executePurchaseInquiryNextAction } from './purchaseInquiryNextActionRuntime.js'

export const PURCHASE_INQUIRY_BUSINESS_BATCH_ACTION = Object.freeze({
  actionCode: 'BATCH_PREPARE_SUPPLIER_QUOTE', minimumSelection: 2,
  outputObject: 'quote_preparation_context', supplierSent: false, purchaseOrderCreated: false,
})
const RESULT_KEY = 'pce.scm.purchase-inquiry.business-batch.v11428186'
let memoryResult = null
const storage = () => typeof window !== 'undefined' ? window.sessionStorage : null

export function loadPurchaseInquiryBusinessBatchResult() {
  if (memoryResult) return memoryResult
  try { return JSON.parse(storage()?.getItem(RESULT_KEY) || 'null') } catch { return null }
}

export function assessPurchaseInquiryBusinessBatchAction(rows = []) {
  const selected = Array.isArray(rows) ? rows : []
  const allowed = selected.length >= PURCHASE_INQUIRY_BUSINESS_BATCH_ACTION.minimumSelection
    && selected.every(item => item.statusCode === 'draft'
      && (item.runtimeState || 'inquiry_draft') === 'inquiry_draft')
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', allowed, selectedCount: selected.length,
    supplierSent: false, purchaseOrderCreated: false })
}

export function executePurchaseInquiryBusinessBatchAction(rows = []) {
  const assessment = assessPurchaseInquiryBusinessBatchAction(rows)
  if (!assessment.allowed) return Object.freeze({ result: 'FAIL', allowed: false, assessment,
    quotePreparationContexts: Object.freeze([]) })
  const executions = rows.map(inquiry => executePurchaseInquiryNextAction(inquiry, 'PREPARE_SUPPLIER_QUOTE'))
  const allowed = executions.every(item => item.result === 'PASS')
  const result = Object.freeze({ result: allowed ? 'PASS' : 'FAIL', allowed, assessment,
    quotePreparationContexts: Object.freeze(executions.map(item => item.quotePreparationContext).filter(Boolean)),
    outputCount: executions.filter(item => item.result === 'PASS').length,
    supplierQuoteCreated: false, supplierSent: false, purchaseOrderCreated: false, productionDataWritten: false })
  memoryResult = result
  try { storage()?.setItem(RESULT_KEY, JSON.stringify(result)) } catch { /* memory fallback */ }
  return result
}
