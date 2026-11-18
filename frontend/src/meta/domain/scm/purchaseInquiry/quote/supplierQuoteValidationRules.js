export const SUPPLIER_QUOTE_VALIDATION_RULES_VERSION = 'V1.14.2.8.5.3'

const present = value => Array.isArray(value) ? value.length > 0 : String(value ?? '').trim().length > 0

export const SUPPLIER_QUOTE_VALIDATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'QUOTE-RULE-001', name: '报价必须关联询价', condition: 'inquiryNo_exists' }),
  Object.freeze({ ruleCode: 'QUOTE-RULE-002', name: '供应商不能为空', condition: 'supplierCode_exists' }),
  Object.freeze({ ruleCode: 'QUOTE-RULE-003', name: '报价明细不能为空', condition: 'quoteLines_exist' }),
  Object.freeze({ ruleCode: 'QUOTE-RULE-004', name: '币种必须一致', condition: 'currency_consistent' }),
  Object.freeze({ ruleCode: 'QUOTE-RULE-005', name: '报价有效期不能过期', condition: 'validUntil_not_expired' }),
])

const evaluateRule = (ruleCode, quote, context) => {
  if (ruleCode === 'QUOTE-RULE-001') return present(quote.inquiryNo)
  if (ruleCode === 'QUOTE-RULE-002') return present(quote.supplierCode)
  if (ruleCode === 'QUOTE-RULE-003') return present(quote.lines)
  if (ruleCode === 'QUOTE-RULE-004') {
    const lineCurrencies = (quote.lines || []).map(line => line.currency).filter(present)
    return present(quote.currency) && present(context.inquiryCurrency)
      && quote.currency === context.inquiryCurrency
      && lineCurrencies.every(currency => currency === quote.currency)
  }
  if (ruleCode === 'QUOTE-RULE-005') {
    const validUntil = Date.parse(quote.validUntil)
    const asOf = Date.parse(context.asOfDate || new Date().toISOString())
    return Number.isFinite(validUntil) && Number.isFinite(asOf) && validUntil >= asOf
  }
  return null
}

export function validateSupplierQuote(quote = {}, context = {}) {
  const results = SUPPLIER_QUOTE_VALIDATION_RULES.map(rule => {
    const decision = evaluateRule(rule.ruleCode, quote, context)
    return Object.freeze({ ruleCode: rule.ruleCode, result: decision === null ? 'UNKNOWN' : decision ? 'PASS' : 'FAIL' })
  })
  const result = results.some(item => item.result === 'UNKNOWN') ? 'UNKNOWN' : results.every(item => item.result === 'PASS') ? 'PASS' : 'FAIL'
  return Object.freeze({ result, rules: Object.freeze(results), businessWriteCount: 0, productionUserDataWritten: false })
}
