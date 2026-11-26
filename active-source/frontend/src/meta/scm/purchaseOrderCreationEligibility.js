import { getScmDocumentStateRule } from '../schema/scm/scmStateRuleRegistry.js'

export const PURCHASE_ORDER_CREATION_ELIGIBILITY_VERSION = 'V1.14.2.8.4.12'

export function buildPurchaseOrderCreationEligibility({ inquiry = {}, inquiryItems = [], existing = null, now = '' } = {}) {
  const rule = getScmDocumentStateRule('purchaseInquiry', inquiry.status)
  const validQuotedLines = inquiryItems.filter((item) => Number(item.quotedPrice || 0) > 0 && item.supplierId)
  const approvedForCreation = Boolean(rule?.mayCreateEligibility)
  const eligibilityStatus = approvedForCreation && validQuotedLines.length > 0 ? 'eligible' : approvedForCreation ? 'blocked' : 'pending'
  const reason = eligibilityStatus === 'eligible'
    ? '询价状态和有效报价满足采购订单生成资格。'
    : eligibilityStatus === 'blocked'
      ? '询价已具备审批状态，但缺少有效供应商报价。'
      : `询价状态 ${inquiry.status || 'unknown'} 尚未具备采购订单生成资格。`
  return Object.freeze({
    id: existing?.id || `po-eligibility-${inquiry.id || 'unknown'}`,
    sourceInquiryId: inquiry.id || '',
    eligibilityStatus: existing?.eligibilityStatus === 'converted' ? 'converted' : eligibilityStatus,
    reason: existing?.eligibilityStatus === 'converted' ? existing.reason : reason,
    createdAt: existing?.createdAt || now || new Date().toISOString(),
    updatedAt: now || new Date().toISOString(),
    convertedPurchaseOrderIds: [...(existing?.convertedPurchaseOrderIds || [])],
  })
}

export function markPurchaseOrderEligibilityConverted(eligibility, purchaseOrderIds = [], now = '') {
  return Object.freeze({
    ...eligibility,
    eligibilityStatus: 'converted',
    reason: '用户确认后已生成采购订单。',
    convertedPurchaseOrderIds: [...purchaseOrderIds],
    updatedAt: now || new Date().toISOString(),
  })
}

