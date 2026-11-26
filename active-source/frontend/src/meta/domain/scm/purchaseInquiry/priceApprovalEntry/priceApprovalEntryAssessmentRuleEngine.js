export const PRICE_APPROVAL_ENTRY_RULE_ENGINE_VERSION = 'V1.14.2.8.6.3'

export const PRICE_APPROVAL_ENTRY_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'PRICE-ENTRY-001', name: '报价证据检查' }),
  Object.freeze({ ruleCode: 'PRICE-ENTRY-002', name: '报价比较检查' }),
  Object.freeze({ ruleCode: 'PRICE-ENTRY-003', name: '核价准备检查' }),
  Object.freeze({ ruleCode: 'PRICE-ENTRY-004', name: '特殊采购人工评审' }),
])

const present = (value) => value !== undefined && value !== null && String(value).trim() !== ''

export function evaluatePriceApprovalEntryAssessment(input = {}) {
  const quotationEvidence = input.quotationEvidence || {}
  const comparison = input.comparison || {}
  const preparation = input.preparation || {}
  const hasAssessmentFacts = present(quotationEvidence.status)
    || present(comparison.comparisonStatus)
    || present(preparation.reviewStatus)
  if (!hasAssessmentFacts) {
    return Object.freeze({
      result: 'NOT_ASSESSED', assessmentStatus: 'not_assessed', rules: Object.freeze([]),
      manualReviewRequired: false, blockedReasons: Object.freeze([]), eligibleForFuturePriceApprovalEntry: false,
      decisionOnly: true, formalPriceApprovalObjectCreated: false, businessWriteCount: 0, productionDataWritten: false,
    })
  }

  const quotationCount = Number(quotationEvidence.quotationCount || 0)
  const evidenceBlocked = quotationEvidence.status === 'blocked' || quotationCount < 1
  const comparisonBlocked = comparison.comparisonStatus === 'blocked'
  const comparisonEligible = ['comparison_ready', 'review_required'].includes(comparison.comparisonStatus)
  const preparationBlocked = preparation.reviewStatus === 'blocked' || (preparation.blockedReasons || []).length > 0
  const preparationEligible = ['prepared', 'pending_review'].includes(preparation.reviewStatus)
  const specialManualReview = input.specialProcurement === true
    || comparison.comparisonStatus === 'review_required'
    || preparation.reviewStatus === 'pending_review'
  const blockedReasons = Object.freeze([
    ...(evidenceBlocked ? ['报价证据不足'] : []),
    ...(comparisonBlocked ? ['报价比较被阻断'] : []),
    ...(preparationBlocked ? ['核价准备被阻断', ...(preparation.blockedReasons || [])] : []),
  ])
  const blocked = evidenceBlocked || comparisonBlocked || preparationBlocked
  const notEligible = !blocked && (!comparisonEligible || !preparationEligible)
  const assessmentStatus = blocked ? 'blocked' : notEligible ? 'not_eligible' : specialManualReview ? 'manual_review' : 'eligible'
  const rules = Object.freeze([
    Object.freeze({ ruleCode: 'PRICE-ENTRY-001', result: evidenceBlocked ? 'FAIL' : 'PASS' }),
    Object.freeze({ ruleCode: 'PRICE-ENTRY-002', result: comparisonBlocked ? 'BLOCKED' : comparisonEligible ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'PRICE-ENTRY-003', result: preparationBlocked ? 'BLOCKED' : preparationEligible ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'PRICE-ENTRY-004', result: specialManualReview ? 'MANUAL_REVIEW' : 'PASS' }),
  ])
  return Object.freeze({
    result: assessmentStatus.toUpperCase(),
    assessmentStatus,
    rules,
    manualReviewRequired: assessmentStatus === 'manual_review',
    blockedReasons,
    eligibleForFuturePriceApprovalEntry: assessmentStatus === 'eligible',
    decisionOnly: true,
    formalPriceApprovalObjectCreated: false,
    approvalSubmitted: false,
    priceApproved: false,
    selectedSupplier: null,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
