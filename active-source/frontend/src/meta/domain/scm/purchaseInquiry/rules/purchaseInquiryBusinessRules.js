export const PURCHASE_INQUIRY_BUSINESS_RULES_VERSION = 'V1.14.2.8.5.2'

const hasValue = value => Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== ''
const positiveCount = value => Number.isFinite(Number(value)) && Number(value) > 0

const defineRule = (ruleCode, name, transition, conditions) => Object.freeze({
  ruleCode,
  name,
  objectCode: 'SCM_PURCHASE_INQUIRY',
  transition: Object.freeze(transition),
  conditions: Object.freeze(conditions),
  evaluationMode: 'read_only',
})

export const PURCHASE_INQUIRY_BUSINESS_RULES = Object.freeze([
  defineRule('INQ-RULE-001', '发布询价条件', { from: 'draft', to: 'issued' }, [
    'inquiryNo_exists',
    'lineCount_gt_0',
    'sourcePurchaseRequest_exists',
    'supplierScope_exists',
  ]),
  defineRule('INQ-RULE-002', '报价接收条件', { from: 'issued', to: 'quoted' }, [
    'quoteCount_gt_0',
    'supplier_exists',
    'quoteLines_exist',
    'currency_consistent',
  ]),
  defineRule('INQ-RULE-003', '进入评估条件', { from: 'quoted', to: 'evaluating' }, [
    'validQuote_exists',
    'quoteComparison_exists',
  ]),
  defineRule('INQ-RULE-004', '批准条件', { from: 'evaluating', to: 'approved' }, [
    'recommendedSupplier_exists',
    'comparisonReason_exists',
  ]),
  defineRule('INQ-RULE-005', '关闭条件', { from: 'approved', to: 'closed' }, [
    'archiveCompleted_true',
    'pendingActionCount_eq_0',
  ]),
])

const CONDITION_EVALUATORS = Object.freeze({
  inquiryNo_exists: facts => hasValue(facts.inquiryNo),
  lineCount_gt_0: facts => positiveCount(facts.lineCount),
  sourcePurchaseRequest_exists: facts => hasValue(facts.sourcePurchaseRequest),
  supplierScope_exists: facts => hasValue(facts.supplierScope),
  quoteCount_gt_0: facts => positiveCount(facts.quoteCount),
  supplier_exists: facts => facts.supplierExists === true || hasValue(facts.supplier) || hasValue(facts.supplierCode),
  quoteLines_exist: facts => positiveCount(facts.quoteLineCount) || hasValue(facts.quoteLines),
  currency_consistent: facts => facts.currencyConsistent === true || (hasValue(facts.quoteCurrency) && facts.quoteCurrency === facts.inquiryCurrency),
  validQuote_exists: facts => facts.validQuoteExists === true || positiveCount(facts.validQuoteCount),
  quoteComparison_exists: facts => facts.quoteComparisonExists === true || hasValue(facts.quoteComparison),
  recommendedSupplier_exists: facts => hasValue(facts.recommendedSupplier),
  comparisonReason_exists: facts => hasValue(facts.comparisonReason),
  archiveCompleted_true: facts => facts.archiveCompleted === true,
  pendingActionCount_eq_0: facts => facts.pendingActionCount !== undefined && facts.pendingActionCount !== null && Number(facts.pendingActionCount) === 0,
})

export function evaluatePurchaseInquiryBusinessRule(input, suppliedFacts = {}) {
  const ruleCode = typeof input === 'string' ? input : input?.ruleCode
  const facts = typeof input === 'string' ? suppliedFacts : input?.facts || input || {}
  const rule = PURCHASE_INQUIRY_BUSINESS_RULES.find(item => item.ruleCode === ruleCode)
  if (!rule) return Object.freeze({ result: 'UNKNOWN', ruleCode, reason: 'BUSINESS_RULE_NOT_REGISTERED' })
  const failedConditions = rule.conditions.filter(condition => !CONDITION_EVALUATORS[condition](facts))
  return Object.freeze({
    result: failedConditions.length === 0 ? 'PASS' : 'FAIL',
    ruleCode,
    reason: failedConditions.length === 0 ? '' : 'BUSINESS_CONDITION_NOT_SATISFIED',
    failedConditions: Object.freeze(failedConditions),
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
