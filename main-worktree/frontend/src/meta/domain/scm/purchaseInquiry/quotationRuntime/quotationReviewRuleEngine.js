export const QUOTATION_REVIEW_RULE_ENGINE_VERSION = 'V1.14.2.8.6.2'

const present = (value) => value !== null && value !== undefined && String(value).trim() !== ''
const positiveAmount = (value) => present(value) && Number.isFinite(Number(value)) && Number(value) >= 0

export const QUOTATION_REVIEW_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'QUOTATION-REVIEW-001', name: '报价数量检查', effect: 'blocked' }),
  Object.freeze({ ruleCode: 'QUOTATION-REVIEW-002', name: '供应商数量检查', effect: 'review_required' }),
  Object.freeze({ ruleCode: 'QUOTATION-REVIEW-003', name: '价格比较完整性', effect: 'blocked' }),
  Object.freeze({ ruleCode: 'QUOTATION-REVIEW-004', name: '禁止自动决策', effect: 'guard' }),
])

export function evaluateQuotationReview(input = {}) {
  const quotations = Array.isArray(input.quotations) ? input.quotations : []
  const supplierCount = new Set(quotations.map((quotation) => quotation.supplierId).filter(present)).size
  const noQuotation = quotations.length < 1
  const incompleteIndexes = quotations.flatMap((quotation, index) => (
    positiveAmount(quotation.price)
      && present(quotation.currency)
      && present(quotation.deliveryDays)
      && Number.isFinite(Number(quotation.deliveryDays))
      && present(quotation.validUntil)
      ? [] : [index]
  ))
  const incomplete = incompleteIndexes.length > 0
  const needsManualReview = !noQuotation && !incomplete && supplierCount < 2
  const comparisonStatus = noQuotation || incomplete ? 'blocked' : needsManualReview ? 'review_required' : 'comparison_ready'
  const blockedReasons = Object.freeze([
    ...(noQuotation ? ['没有报价证据'] : []),
    ...(incomplete ? ['报价金额、币种、交期或有效期不完整'] : []),
  ])
  const rules = Object.freeze([
    Object.freeze({ ruleCode: 'QUOTATION-REVIEW-001', result: noQuotation ? 'FAIL' : 'PASS' }),
    Object.freeze({ ruleCode: 'QUOTATION-REVIEW-002', result: supplierCount < 2 ? 'REVIEW_REQUIRED' : 'PASS' }),
    Object.freeze({ ruleCode: 'QUOTATION-REVIEW-003', result: incomplete ? 'FAIL' : 'PASS', incompleteQuotationIndexes: Object.freeze(incompleteIndexes) }),
    Object.freeze({ ruleCode: 'QUOTATION-REVIEW-004', result: 'PASS', autoSupplierSelection: false, autoPriceApproval: false }),
  ])
  return Object.freeze({
    result: comparisonStatus === 'blocked' ? 'BLOCKED' : comparisonStatus === 'review_required' ? 'REVIEW_REQUIRED' : 'PASS',
    comparisonStatus,
    quotationCount: quotations.length,
    supplierCount,
    blockedReasons,
    rules,
    decisionOnly: true,
    selectedSupplier: null,
    priceReviewObjectCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
