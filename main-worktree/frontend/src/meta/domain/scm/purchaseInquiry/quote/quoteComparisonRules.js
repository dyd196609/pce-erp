export const QUOTE_COMPARISON_RULES_VERSION = 'V1.14.2.8.5.3'

export const QUOTE_COMPARISON_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'COMPARISON-RULE-001', name: '至少一个有效报价', condition: 'valid_quote_exists' }),
  Object.freeze({ ruleCode: 'COMPARISON-RULE-002', name: '比较条件存在', condition: 'evaluation_criteria_exists' }),
  Object.freeze({ ruleCode: 'COMPARISON-RULE-003', name: '推荐供应商必须有依据', condition: 'recommendation_has_reason' }),
])

const isValidQuote = quote => Boolean(quote?.quoteNo) && (quote.valid === true || quote.validationResult === 'PASS' || ['valid', 'validated'].includes(quote.status))
const hasItems = value => Array.isArray(value) && value.length > 0
const present = value => String(value ?? '').trim().length > 0

export function evaluateQuoteComparison(input = {}) {
  const quoteList = Array.isArray(input.quoteList) ? input.quoteList : []
  const validQuotes = quoteList.filter(isValidQuote)
  const validQuoteCount = Number.isFinite(Number(input.validQuoteCount)) ? Number(input.validQuoteCount) : validQuotes.length
  const results = Object.freeze([
    Object.freeze({ ruleCode: 'COMPARISON-RULE-001', result: validQuoteCount > 0 ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'COMPARISON-RULE-002', result: hasItems(input.evaluationCriteria) ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'COMPARISON-RULE-003', result: present(input.recommendedSupplier) && present(input.comparisonReason) ? 'PASS' : 'FAIL' }),
  ])
  return Object.freeze({
    result: results.every(rule => rule.result === 'PASS') ? 'PASS' : 'FAIL',
    rules: results,
    eligibleQuoteCount: validQuoteCount,
    emptyQuoteParticipationAllowed: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
