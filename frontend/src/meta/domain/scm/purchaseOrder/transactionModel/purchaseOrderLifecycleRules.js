import { PURCHASE_ORDER_LIFECYCLE_STATES } from './purchaseOrderLifecycleStateDefinition.js'

export const PURCHASE_ORDER_LIFECYCLE_RULES_VERSION = 'V1.14.2.8.5.9'
export const PURCHASE_ORDER_LIFECYCLE_RULE_SET_CODE = 'SCM_PURCHASE_ORDER_LIFECYCLE_RULES'

export const PURCHASE_ORDER_LIFECYCLE_RULES = Object.freeze([
  Object.freeze({ from: 'draft', to: Object.freeze(['pending_approval', 'cancelled']) }),
  Object.freeze({ from: 'pending_approval', to: Object.freeze(['approved', 'cancelled']) }),
  Object.freeze({ from: 'approved', to: Object.freeze(['issued', 'cancelled']) }),
  Object.freeze({ from: 'issued', to: Object.freeze(['partially_received', 'completed', 'cancelled']) }),
  Object.freeze({ from: 'partially_received', to: Object.freeze(['completed', 'cancelled']) }),
  Object.freeze({ from: 'completed', to: Object.freeze([]) }),
  Object.freeze({ from: 'cancelled', to: Object.freeze([]) }),
])

export function evaluatePurchaseOrderLifecycleRule({ from, to } = {}) {
  if (!from || !to) return Object.freeze({ result: 'UNKNOWN', eligible: false, reason: 'lifecycle_rule_fact_missing', transitionExecuted: false })
  if (!PURCHASE_ORDER_LIFECYCLE_STATES.includes(from) || !PURCHASE_ORDER_LIFECYCLE_STATES.includes(to)) return Object.freeze({ result: 'FAIL', eligible: false, reason: 'lifecycle_status_not_defined', transitionExecuted: false })
  const rule = PURCHASE_ORDER_LIFECYCLE_RULES.find(item => item.from === from)
  const eligible = rule?.to.includes(to) === true
  return Object.freeze({
    result: eligible ? 'PASS' : 'FAIL',
    eligible,
    reason: eligible ? '' : 'lifecycle_relationship_not_defined',
    definitionOnly: true,
    automaticTransitionAllowed: false,
    transitionExecutionAllowed: false,
    transitionExecuted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
