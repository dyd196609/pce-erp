export const SUPPLIER_RECOMMENDATION_VALIDATION_RULES_VERSION = 'V1.14.2.8.5.4'

const present = value => Array.isArray(value) ? value.length > 0 : String(value ?? '').trim().length > 0

export const SUPPLIER_RECOMMENDATION_VALIDATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-001', field: 'inquiryId', description: '必须关联询价' }),
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-002', field: 'quoteComparisonId', description: '必须关联报价比较' }),
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-003', field: 'recommendedSupplierId', description: '必须存在推荐供应商' }),
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-004', field: 'recommendationReason', description: '必须存在推荐理由' }),
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-005', field: 'evidenceReferences', description: '必须存在证据引用' }),
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-006', field: 'recommendationStatus', description: '必须存在推荐状态' }),
  Object.freeze({ ruleCode: 'REC-DECISION-RULE-007', field: 'approvalRequired', description: '必须明确是否需要审批' }),
])

export function validateSupplierRecommendationDecision(input = {}) {
  const results = SUPPLIER_RECOMMENDATION_VALIDATION_RULES.map(rule => {
    const valid = rule.field === 'approvalRequired' ? typeof input.approvalRequired === 'boolean' : present(input[rule.field])
    return Object.freeze({ ruleCode: rule.ruleCode, result: valid ? 'PASS' : 'FAIL' })
  })
  return Object.freeze({
    result: results.every(rule => rule.result === 'PASS') ? 'PASS' : 'FAIL',
    rules: Object.freeze(results),
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
