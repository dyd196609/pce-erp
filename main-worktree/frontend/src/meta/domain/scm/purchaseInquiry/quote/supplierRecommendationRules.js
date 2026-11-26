export const SUPPLIER_RECOMMENDATION_RULES_VERSION = 'V1.14.2.8.5.3'
export const SUPPLIER_RECOMMENDATION_RULE_CODE = 'SCM_SUPPLIER_RECOMMENDATION_RULE'

const present = value => Array.isArray(value) ? value.length > 0 : String(value ?? '').trim().length > 0
const isValidQuote = quote => Boolean(quote?.quoteNo) && (quote.valid === true || quote.validationResult === 'PASS' || ['valid', 'validated'].includes(quote.status))

export function evaluateSupplierRecommendation(input = {}) {
  const validQuoteExists = input.validQuoteExists === true
    || Number(input.validQuoteCount) > 0
    || (Array.isArray(input.validQuotes) && input.validQuotes.some(isValidQuote))
  const comparisonCompleted = input.comparisonCompleted === true
  const recommendationComplete = present(input.recommendedSupplier) && present(input.reason) && present(input.evidence)
  const pass = validQuoteExists && comparisonCompleted && recommendationComplete
  return Object.freeze({
    result: pass ? 'PASS' : 'FAIL',
    ruleCode: SUPPLIER_RECOMMENDATION_RULE_CODE,
    recommendedSupplier: pass ? input.recommendedSupplier : null,
    reason: pass ? input.reason : '',
    evidence: pass ? Object.freeze(Array.isArray(input.evidence) ? [...input.evidence] : [input.evidence]) : Object.freeze([]),
    createsPurchaseOrder: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
