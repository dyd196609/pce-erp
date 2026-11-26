import { PURCHASE_ORDER_CREATION_RULES, evaluatePurchaseOrderCreationCondition } from './purchaseOrderCreationRules.js'

export const PURCHASE_ORDER_CREATION_ELIGIBILITY_VERSION = 'V1.14.2.8.5.5'
export const PURCHASE_ORDER_CREATION_ELIGIBILITY_CODE = 'SCM_PURCHASE_ORDER_CREATION_ELIGIBILITY'

export function evaluatePurchaseOrderCreationEligibility(facts = {}) {
  const evaluatedConditions = Object.freeze(PURCHASE_ORDER_CREATION_RULES.map(rule => Object.freeze({
    conditionCode: rule.conditionCode,
    ...evaluatePurchaseOrderCreationCondition(rule.ruleCode, facts),
  })))
  const blockingReasons = Object.freeze(evaluatedConditions.filter(item => item.result !== 'PASS').map(item => item.conditionCode))
  const eligible = blockingReasons.length === 0
  return Object.freeze({
    gateStatus: 'evaluated',
    eligibilityResult: eligible ? 'ELIGIBLE' : 'BLOCKED',
    eligible,
    blockingReasons,
    riskWarnings: Object.freeze(Array.isArray(facts.riskWarnings) ? [...facts.riskWarnings] : []),
    evaluatedConditions,
    decisionOnly: true,
    createsPurchaseOrder: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}
