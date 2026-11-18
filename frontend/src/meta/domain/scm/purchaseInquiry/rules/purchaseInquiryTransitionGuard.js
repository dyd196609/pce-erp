import { PURCHASE_INQUIRY_LIFECYCLE } from '../purchaseInquiryStatusModel.js'
import { evaluatePurchaseInquiryBusinessRule } from './purchaseInquiryBusinessRules.js'
import { resolvePurchaseInquiryTransitionRule } from './purchaseInquiryStateTransitionRules.js'

export const PURCHASE_INQUIRY_TRANSITION_GUARD_VERSION = 'V1.14.2.8.5.2'
export const PURCHASE_INQUIRY_TRANSITION_GUARD_REASONS = Object.freeze({
  reverse: 'reverse_transition_forbidden',
  skip: 'skip_transition_forbidden',
})

export function evaluatePurchaseInquiryTransitionGuard({ fromStatus, toStatus, facts = {} } = {}) {
  if (!fromStatus || !toStatus) return Object.freeze({ result: 'UNKNOWN', reason: 'transition_fact_missing' })
  const fromIndex = PURCHASE_INQUIRY_LIFECYCLE.indexOf(fromStatus)
  const toIndex = PURCHASE_INQUIRY_LIFECYCLE.indexOf(toStatus)
  if (fromIndex < 0 || toIndex < 0) return Object.freeze({ result: 'UNKNOWN', reason: 'transition_status_not_registered' })
  if (toIndex <= fromIndex) return Object.freeze({ result: 'FAIL', reason: PURCHASE_INQUIRY_TRANSITION_GUARD_REASONS.reverse })
  if (toIndex !== fromIndex + 1) return Object.freeze({ result: 'FAIL', reason: PURCHASE_INQUIRY_TRANSITION_GUARD_REASONS.skip })
  const transitionRule = resolvePurchaseInquiryTransitionRule(fromStatus, toStatus)
  if (!transitionRule) return Object.freeze({ result: 'UNKNOWN', reason: 'transition_rule_not_registered' })
  const businessRule = evaluatePurchaseInquiryBusinessRule(transitionRule.businessRuleCode, facts)
  return Object.freeze({
    ...businessRule,
    fromStatus,
    toStatus,
    transitionRuleCode: transitionRule.ruleCode,
    businessRuleCode: transitionRule.businessRuleCode,
  })
}
