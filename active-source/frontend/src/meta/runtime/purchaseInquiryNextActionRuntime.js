import { evaluatePurchaseInquiryNextAction } from '../process/scm/purchaseInquiry/purchaseInquiryNextActionContract.js'
import { createPurchaseInquirySupplierQuoteHandoff } from '../process/scm/purchaseInquiry/purchaseInquirySupplierQuoteHandoff.js'
import { ensurePurchaseInquiryRuntimeDraft, updatePurchaseInquiryRuntimeState } from './purchaseInquiryRuntime.js'

export const PURCHASE_INQUIRY_NEXT_ACTION_RUNTIME_VERSION = 'V1.14.2.8.18.7A'
export const PURCHASE_INQUIRY_QUOTE_PREPARATION_CONTEXT_KEY = 'pce.scm.purchase-inquiry.quote-preparation.v11428187a'
const memoryContexts = []
const storage = () => typeof window !== 'undefined' ? window.localStorage : null

function readContexts() {
  const target = storage()
  if (!target) return [...memoryContexts]
  try { return JSON.parse(target.getItem(PURCHASE_INQUIRY_QUOTE_PREPARATION_CONTEXT_KEY) || '[]') } catch { return [...memoryContexts] }
}
function writeContexts(contexts) {
  memoryContexts.splice(0, memoryContexts.length, ...contexts)
  try { storage()?.setItem(PURCHASE_INQUIRY_QUOTE_PREPARATION_CONTEXT_KEY, JSON.stringify(contexts)) } catch { /* memory fallback */ }
}

export function listPurchaseInquiryQuotePreparationContexts() {
  return Object.freeze(readContexts().map(item => Object.freeze(item)))
}

export function executePurchaseInquiryNextAction(inquiry = {}, actionCode = '') {
  const decision = evaluatePurchaseInquiryNextAction(inquiry, actionCode)
  const sourceRuntimeState = inquiry.runtimeState || (inquiry.statusCode === 'draft' ? 'inquiry_draft' : '')
  if (!decision.allowed || actionCode !== 'PREPARE_SUPPLIER_QUOTE' || sourceRuntimeState !== 'inquiry_draft') {
    return Object.freeze({ result: 'FAIL', allowed: false, actionCode, reason: 'PURCHASE_INQUIRY_NEXT_ACTION_NOT_ALLOWED' })
  }
  const runtimeInquiry = ensurePurchaseInquiryRuntimeDraft(inquiry)
  if (runtimeInquiry.runtimeState !== 'inquiry_draft') return Object.freeze({ result: 'FAIL', allowed: false,
    actionCode, reason: 'PURCHASE_INQUIRY_DRAFT_STATE_REQUIRED' })
  const handoff = createPurchaseInquirySupplierQuoteHandoff(runtimeInquiry)
  if (!handoff.valid) return Object.freeze({ result: 'FAIL', allowed: false, actionCode, handoff })
  const contexts = readContexts()
  const existingIndex = contexts.findIndex(item => item.inquiryNo === inquiry.inquiryNo)
  if (existingIndex < 0) contexts.push(handoff.context)
  else contexts.splice(existingIndex, 1, handoff.context)
  writeContexts(contexts)
  const updatedInquiry = updatePurchaseInquiryRuntimeState(inquiry.inquiryNo, 'quote_preparation_ready')
  return Object.freeze({ result: 'PASS', allowed: true, actionCode,
    fromState: 'inquiry_draft', toState: 'quote_preparation_ready', inquiry: updatedInquiry,
    quotePreparationContext: handoff.context, handoff, supplierQuoteCreated: false,
    supplierSent: false, purchaseOrderCreated: false, productionDataWritten: false })
}
