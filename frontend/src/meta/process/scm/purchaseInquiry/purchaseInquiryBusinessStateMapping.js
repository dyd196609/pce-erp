export const PURCHASE_INQUIRY_BUSINESS_STATE_MAPPING_VERSION = 'V1.14.2.8.18.8.1'

const PROCESS_STATES = Object.freeze({
  inquiry_draft: Object.freeze({ processStatusCode: 'inquiry_draft', processStatusLabel: '询价编辑中',
    currentNode: '询价', nextAction: '准备供应商报价' }),
  inquiry_editing: Object.freeze({ processStatusCode: 'inquiry_draft', processStatusLabel: '询价编辑中',
    currentNode: '询价', nextAction: '保存询价或准备供应商报价' }),
  quote_preparation_ready: Object.freeze({ processStatusCode: 'quote_preparation_ready',
    processStatusLabel: '已进入供应商报价准备', currentNode: '供应商报价准备', nextAction: '进入供应商报价准备' }),
})

export function resolvePurchaseInquiryBusinessState(inquiry = {}) {
  const businessStatusCode = inquiry.statusCode || inquiry.status || 'draft'
  const runtimeState = inquiry.runtimeState || 'inquiry_draft'
  const process = PROCESS_STATES[runtimeState] || Object.freeze({ processStatusCode: runtimeState,
    processStatusLabel: runtimeState, currentNode: '询价', nextAction: '检查询价状态' })
  return Object.freeze({
    businessStatusCode,
    businessStatusLabel: inquiry.statusLabel || (businessStatusCode === 'draft' ? '草稿' : businessStatusCode),
    runtimeState,
    ...process,
  })
}

export function validatePurchaseInquiryBusinessStateMapping(inquiry = {}) {
  const state = resolvePurchaseInquiryBusinessState(inquiry)
  const valid = Boolean(state.businessStatusCode && state.businessStatusLabel
    && state.processStatusCode && state.processStatusLabel && state.currentNode && state.nextAction)
    && (state.runtimeState !== 'quote_preparation_ready'
      || (state.businessStatusLabel === '草稿' && state.processStatusLabel === '已进入供应商报价准备'))
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, state })
}
