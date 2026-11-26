import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_INQUIRY_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_INQUIRY_RUNTIME_STATE',
  objectType: 'PurchaseInquiry',
  initialState: 'preparation_ready',
  states: ['preparation_ready', 'inquiry_draft', 'inquiry_editing', 'quote_preparation_ready'],
  transitions: [
    { actionCode: 'START_PURCHASE_INQUIRY', from: 'preparation_ready', to: 'inquiry_draft' },
    { actionCode: 'EDIT_PURCHASE_INQUIRY', from: 'inquiry_draft', to: 'inquiry_editing' },
    { actionCode: 'SAVE_PURCHASE_INQUIRY', from: 'inquiry_editing', to: 'inquiry_draft' },
    { actionCode: 'PREPARE_SUPPLIER_QUOTE', from: 'inquiry_draft', to: 'quote_preparation_ready' },
  ],
})

export const PURCHASE_INQUIRY_STATE_BOUNDARIES = Object.freeze({
  preparation_ready: Object.freeze({ objectType: 'InquiryPreparationBatch', formalInquiryCreated: false }),
  inquiry_draft: Object.freeze({ objectType: 'PurchaseInquiry', formalInquiryCreated: true, supplierSent: false }),
  inquiry_editing: Object.freeze({ objectType: 'PurchaseInquiry', persistenceMode: 'session_runtime', supplierSent: false }),
  quote_preparation_ready: Object.freeze({ objectType: 'QuotePreparationContext', supplierQuoteCreated: false, supplierSent: false }),
})

export const PURCHASE_INQUIRY_PAGE_STATE_OPTIONS = Object.freeze([
  Object.freeze({ label: '草稿', value: 'draft', runtimeState: 'inquiry_draft' }),
])

export const PURCHASE_INQUIRY_FORBIDDEN_DIRECT_STATES = Object.freeze(['quote', 'comparison', 'purchase_order'])

export function validatePurchaseInquiryDraftOperationState(inquiry = {}) {
  const valid = inquiry.statusCode === 'draft'
    && ['inquiry_draft', 'inquiry_editing'].includes(inquiry.runtimeState)
    && PURCHASE_INQUIRY_FORBIDDEN_DIRECT_STATES.every(state => inquiry.runtimeState !== state)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}

export function validatePurchaseInquiryStateBoundary() {
  const preparation = PURCHASE_INQUIRY_STATE_BOUNDARIES.preparation_ready
  const draft = PURCHASE_INQUIRY_STATE_BOUNDARIES.inquiry_draft
  const editing = PURCHASE_INQUIRY_STATE_BOUNDARIES.inquiry_editing
  const valid = preparation.objectType === 'InquiryPreparationBatch' && preparation.formalInquiryCreated === false
    && draft.objectType === 'PurchaseInquiry' && draft.formalInquiryCreated === true
    && draft.supplierSent === false && editing.persistenceMode === 'session_runtime' && editing.supplierSent === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, transition: 'preparation_ready->inquiry_draft' })
}
