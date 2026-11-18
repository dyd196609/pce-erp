import { PURCHASE_INQUIRY_LIFECYCLE } from '../purchaseInquiryStatusModel.js'

export const PURCHASE_INQUIRY_STATE_TRANSITION_RULES_VERSION = 'V1.14.2.8.5.2'
export const PURCHASE_INQUIRY_STATE_TRANSITION_RULE_CODE = 'SCM_PURCHASE_INQUIRY_STATE_TRANSITION_RULES'

const BUSINESS_RULE_CODES = Object.freeze([
  'INQ-RULE-001',
  'INQ-RULE-002',
  'INQ-RULE-003',
  'INQ-RULE-004',
  'INQ-RULE-005',
])

export const PURCHASE_INQUIRY_STATE_TRANSITION_RULES = Object.freeze(
  PURCHASE_INQUIRY_LIFECYCLE.slice(0, -1).map((fromStatus, index) => Object.freeze({
    ruleCode: PURCHASE_INQUIRY_STATE_TRANSITION_RULE_CODE,
    objectCode: 'SCM_PURCHASE_INQUIRY',
    from: fromStatus,
    to: PURCHASE_INQUIRY_LIFECYCLE[index + 1],
    fromStatus,
    toStatus: PURCHASE_INQUIRY_LIFECYCLE[index + 1],
    businessRuleCode: BUSINESS_RULE_CODES[index],
    transitionPolicy: 'adjacent_forward_only',
    executionMode: 'read_only',
  })),
)

export function resolvePurchaseInquiryTransitionRule(fromStatus, toStatus) {
  return PURCHASE_INQUIRY_STATE_TRANSITION_RULES.find(rule => rule.fromStatus === fromStatus && rule.toStatus === toStatus) || null
}
