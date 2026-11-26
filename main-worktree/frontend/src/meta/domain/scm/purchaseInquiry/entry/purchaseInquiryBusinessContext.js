import { PURCHASE_INQUIRY_ENTRY_CONTRACT } from './purchaseInquiryEntryContract.js'

const text = value => String(value ?? '').trim()

export function resolvePurchaseInquiryBusinessContext({ query = {}, preparations = [], inquiries = [] } = {}) {
  const preparationNo = text(query.inquiryPreparationNo)
  const sourceRequestNo = text(query.sourceRequestNo)
  const inquiryIdentity = text(query.inquiryNo || query.inquiryId)
  const preparation = preparations.find(item => item.inquiryPreparationNo === preparationNo)
    || preparations.find(item => sourceRequestNo && item.sourceRequestNo === sourceRequestNo) || null
  const inquiry = inquiries.find(item => item.inquiryNo === inquiryIdentity || String(item.id) === inquiryIdentity)
    || inquiries.find(item => preparation && item.sourcePreparationNo === preparation.inquiryPreparationNo) || null
  if (preparation) return Object.freeze({ contractCode: PURCHASE_INQUIRY_ENTRY_CONTRACT.contractCode,
    entryType: 'purchase_request_preparation', businessSource: '采购申请 → 询价准备',
    sourceNo: preparation.sourceRequestNo, preparationNo: preparation.inquiryPreparationNo,
    currentInquiryNo: inquiry?.inquiryNo || '', currentStatus: inquiry?.statusLabel || preparation.statusLabel,
    nextAction: inquiry ? '查看询价' : '启动询价', creationContextComplete: true, browseOnly: false })
  if (inquiry) return Object.freeze({ contractCode: PURCHASE_INQUIRY_ENTRY_CONTRACT.contractCode,
    entryType: 'existing_purchase_inquiry', businessSource: '现有正式询价', sourceNo: inquiry.sourceRequestNo || inquiry.inquiryNo,
    preparationNo: inquiry.sourcePreparationNo || '', currentInquiryNo: inquiry.inquiryNo,
    currentStatus: inquiry.statusLabel, nextAction: '查看询价', creationContextComplete: false, browseOnly: true })
  return Object.freeze({ contractCode: PURCHASE_INQUIRY_ENTRY_CONTRACT.contractCode,
    entryType: 'business_process_center_browse', businessSource: '业务流程中心', sourceNo: '无来源上下文',
    preparationNo: '', currentInquiryNo: '', currentStatus: '未选择询价对象', nextAction: '请选择已有询价查看',
    creationContextComplete: false, browseOnly: true })
}

export function validatePurchaseInquiryBusinessContext(context = {}) {
  const valid = PURCHASE_INQUIRY_ENTRY_CONTRACT.allowedEntryTypes.includes(context.entryType)
    && Boolean(context.businessSource) && Boolean(context.sourceNo) && Boolean(context.currentStatus) && Boolean(context.nextAction)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
