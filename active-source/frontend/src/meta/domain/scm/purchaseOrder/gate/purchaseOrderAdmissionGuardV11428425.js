export const PURCHASE_ORDER_ADMISSION_GUARD_VERSION_V11428425 = 'V1.14.2.8.4.25'

const text = value => String(value ?? '').trim()
const list = value => Array.isArray(value) ? value : []
const freeze = value => Object.freeze(value)

function check(checkCode, checkName, currentValue, passed, blockedReason) {
  return freeze({ checkCode, checkName, passed: Boolean(passed),
    currentValue, result: passed ? 'PASS' : 'FAIL',
    reason: passed ? '条件满足' : blockedReason,
    blockedReason: passed ? '' : blockedReason })
}

export function evaluatePurchaseOrderAdmissionGuardV11428425({
  gate = {}, decisionBatchResult = {}, checkedBy = '',
} = {}) {
  const recommendationItems = list(gate.recommendationItems)
  const checks = freeze([
    check('RECOMMENDATION_EXISTS', '存在供应商推荐',
      `decision=${text(gate.recommendationDecisionId) || 'missing'};items=${recommendationItems.length}`,
      gate.objectType === 'SupplierRecommendationGate'
        && text(gate.recommendationDecisionId) && recommendationItems.length > 0
        && recommendationItems.every(item => text(item.selectedSupplierCode
          || item.decisionSupplier?.supplierCode)),
      '供应商推荐决策不存在或推荐供应商不完整'),
    check('RECOMMENDATION_MANUALLY_CONFIRMED', '推荐已人工确认',
      `decisionStatus=${text(decisionBatchResult.status) || 'missing'};gateStatus=${text(gate.status) || 'missing'};confirmedBy=${text(gate.confirmedBy) || 'missing'}`,
      decisionBatchResult.objectType === 'SupplierRecommendationDecisionBatchResult'
        && decisionBatchResult.status === 'confirmed'
        && recommendationItems.every(item => item.reviewStatus === 'confirmed'
          && text(item.reviewer) && text(item.reviewedAt))
        && gate.status === 'CONFIRMED' && text(gate.confirmedBy) && text(gate.confirmedAt),
      '供应商推荐或采购订单Gate尚未完成人工确认'),
    check('QUOTE_EVIDENCE_EXISTS', '报价依据存在',
      `quoteComparisonId=${text(gate.quoteComparisonId) || 'missing'};evidenceCount=${list(gate.quoteEvidence).length}`,
      text(gate.quoteComparisonId) && list(gate.quoteEvidence).length > 0,
      '缺少报价比较编号或供应商报价依据'),
    check('PRICE_APPROVAL_EVIDENCE_READY', '核价依据满足',
      `priceApprovalId=${text(gate.priceApprovalId) || 'missing'};evidenceCount=${list(gate.priceEvidence).length}`,
      text(gate.priceApprovalId) && list(gate.priceEvidence).length > 0,
      '缺少核价编号或核价证据'),
    check('SOURCE_CHAIN_COMPLETE', '来源链完整',
      `${text(gate.purchaseRequestId) || 'missing'} -> ${text(gate.inquiryId) || 'missing'} -> ${text(gate.quoteComparisonId) || 'missing'} -> ${text(gate.priceApprovalId) || 'missing'} -> ${text(gate.recommendationDecisionId) || 'missing'}`,
      text(gate.purchaseRequestId) && text(gate.inquiryId)
        && text(gate.quoteComparisonId) && text(gate.priceApprovalId)
        && text(gate.recommendationDecisionId),
      '采购申请、询价、报价比较、核价或推荐决策来源链不完整'),
  ])
  const blockedReasons = freeze(checks.filter(item => !item.passed)
    .map(item => item.blockedReason))
  return freeze({
    objectType: 'PurchaseOrderAdmissionGuardResult',
    guardCode: 'PURCHASE_ORDER_ADMISSION_GUARD_V11428425',
    checkedBy: text(checkedBy),
    checks,
    blockedReasons,
    result: blockedReasons.length ? 'FAIL' : 'PASS',
    purchaseOrderCreationAllowed: blockedReasons.length === 0,
    purchaseOrderCreated: false,
    automaticPurchaseOrderCreation: false,
  })
}
