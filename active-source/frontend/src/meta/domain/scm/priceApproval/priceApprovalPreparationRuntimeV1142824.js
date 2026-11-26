export const PRICE_APPROVAL_PREPARATION_RUNTIME_VERSION = 'V1.14.2.8.4.24'

export const PRICE_APPROVAL_STATUS_TRANSITIONS = Object.freeze({
  draft: Object.freeze(['reviewing']),
  reviewing: Object.freeze(['completed']),
  completed: Object.freeze(['reviewing']),
})

export const PRICE_APPROVAL_REVIEW_RESULT_LABELS = Object.freeze({
  pass: '通过', reject: '不同意', adjust: '调整后重新核价',
})

const text = value => String(value || '').trim()
const clone = value => JSON.parse(JSON.stringify(value ?? null))

function assertPreparation(preparation = {}) {
  if (preparation.objectType !== 'PriceApprovalPreparation'
    || !['QuoteComparisonFact', 'QuoteComparisonFactProjection'].includes(preparation.factSource)
    || !preparation.approvalPrepareNo || !preparation.sourceComparisonNo
    || !preparation.sourceQuotationEvidence?.length
    || !preparation.supplierCandidates?.length || !preparation.materialLines?.length) {
    throw new Error('PRICE_APPROVAL_PREPARATION_INCOMPLETE')
  }
}

export function resolvePriceApprovalReviewResult(preparation = {}) {
  if (PRICE_APPROVAL_REVIEW_RESULT_LABELS[preparation.reviewResult]) return preparation.reviewResult
  const opinion = text(preparation.approvalOpinion).toLowerCase()
  if (['同意', '通过', 'approve', 'approved', 'pass'].includes(opinion)) return 'pass'
  if (['不同意', '拒绝', '驳回', 'reject', 'rejected'].includes(opinion)) return 'reject'
  if (opinion.includes('调整') || opinion.includes('重新核价')) return 'adjust'
  return ''
}

export function resolvePriceApprovalProcessStatus(preparation = {}) {
  return ['approved', 'rejected'].includes(preparation.status) ? 'completed' : preparation.status
}

export function hasReceivedQuotationEvidence(preparation = {}) {
  const evidence = preparation.sourceQuotationEvidence || []
  return evidence.length > 0 && evidence.every(item =>
    text(item.quotationStatusCode || item.quotationStatus) === 'quotation_received')
}

export function resolveSupplierRecommendationBlockedReason(preparation = {}) {
  if (resolvePriceApprovalProcessStatus(preparation) !== 'completed'
    || resolvePriceApprovalReviewResult(preparation) !== 'pass') {
    return '当前核价结果未通过，不允许进入供应商推荐。'
  }
  if (!hasReceivedQuotationEvidence(preparation)) {
    return '当前供应商报价尚未全部接收，不允许进入供应商推荐。'
  }
  return ''
}

export function startPriceApprovalReview(preparation = {}) {
  assertPreparation(preparation)
  const currentStatus = resolvePriceApprovalProcessStatus(preparation)
  if (!PRICE_APPROVAL_STATUS_TRANSITIONS[currentStatus]?.includes('reviewing')
    || (currentStatus === 'completed' && resolvePriceApprovalReviewResult(preparation) !== 'adjust')) {
    throw new Error('PRICE_APPROVAL_STATUS_TRANSITION_NOT_ALLOWED')
  }
  return Object.freeze({ ...clone(preparation), status: 'reviewing', statusLabel: '核价中',
    automaticLowestQuoteSelected: false, supplierRecommendationCreated: false,
    purchaseOrderCreated: false })
}

export function completePriceApprovalReview(preparation = {}, input = {}, targetStatus = 'approved') {
  assertPreparation(preparation)
  const reviewResult = text(input.reviewResult)
    || ({ approved: 'pass', rejected: 'reject' })[targetStatus]
  const nextStatus = 'completed'
  if (!PRICE_APPROVAL_STATUS_TRANSITIONS[resolvePriceApprovalProcessStatus(preparation)]?.includes(nextStatus)) {
    throw new Error('PRICE_APPROVAL_STATUS_TRANSITION_NOT_ALLOWED')
  }
  const supplierCode = text(input.selectedSupplierCode)
  const selected = preparation.supplierCandidates.find(item =>
    text(item.supplierCode || item.supplierId) === supplierCode)
  if (!PRICE_APPROVAL_REVIEW_RESULT_LABELS[reviewResult]) throw new Error('PRICE_APPROVAL_REVIEW_RESULT_REQUIRED')
  if (reviewResult === 'pass' && !selected) throw new Error('PRICE_APPROVAL_SELECTED_SUPPLIER_REQUIRED')
  if (!text(input.reviewOpinion) || !text(input.approvalOpinion) || !text(input.reviewer)) {
    throw new Error('PRICE_APPROVAL_MANUAL_DECISION_INCOMPLETE')
  }
  const completed = { ...clone(preparation), selectedSupplier: clone(selected || {}),
    reviewOpinion: text(input.reviewOpinion), exceptionNote: text(input.exceptionNote),
    approvalOpinion: text(input.approvalOpinion), reviewer: text(input.reviewer),
    reviewedAt: input.reviewedAt || new Date().toISOString(),
    decisionVersion: Number(preparation.decisionVersion || 0) + 1,
    status: nextStatus, statusCode: nextStatus, statusLabel: '已完成', reviewResult,
    reviewResultLabel: PRICE_APPROVAL_REVIEW_RESULT_LABELS[reviewResult],
    automaticLowestQuoteSelected: false, supplierRecommendationCreated: false,
    purchaseOrderCreated: false }
  const supplierRecommendationBlockedReason = resolveSupplierRecommendationBlockedReason(completed)
  return Object.freeze({ ...completed,
    supplierRecommendationEligible: !supplierRecommendationBlockedReason,
    supplierRecommendationBlockedReason })
}

export function createSupplierRecommendationDecisionContext(preparation = {}) {
  assertPreparation(preparation)
  const reviewResult = resolvePriceApprovalReviewResult(preparation)
  const blockedReason = resolveSupplierRecommendationBlockedReason(preparation)
  if (blockedReason) throw new Error(blockedReason)
  if (!preparation.selectedSupplier?.supplierCode) throw new Error('PRICE_APPROVAL_SELECTED_SUPPLIER_REQUIRED')
  return Object.freeze({
    objectType: 'SupplierRecommendationDecisionContext',
    sourcePriceApprovalPreparationNo: preparation.approvalPrepareNo,
    sourceComparisonNo: preparation.sourceComparisonNo,
    materialLines: clone(preparation.materialLines),
    supplierCandidates: clone(preparation.supplierCandidates),
    selectedSupplier: clone(preparation.selectedSupplier),
    reviewResult,
    reviewResultLabel: PRICE_APPROVAL_REVIEW_RESULT_LABELS[reviewResult],
    priceEvidence: clone(preparation.sourceQuotationEvidence),
    historicalPriceEvidence: clone(preparation.historicalPriceReference || []),
    manualAssessment: Object.freeze({ reviewOpinion: preparation.reviewOpinion,
      exceptionNote: preparation.exceptionNote, approvalOpinion: preparation.approvalOpinion,
      reviewer: preparation.reviewer, reviewedAt: preparation.reviewedAt,
      decisionVersion: preparation.decisionVersion }),
    status: 'context_ready', purchaseOrderCreated: false,
  })
}
