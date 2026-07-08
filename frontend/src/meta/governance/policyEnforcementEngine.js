import { runReviewControlLoop } from '../review/reviewControlEngine.js'
import { processRealWorldFeedback } from '../reality/realityFeedbackEngine.js'

export function enforceBusinessRules(context = {}) {
  const review = runReviewControlLoop(context.schema || {})
  const reality = context.reality || processRealWorldFeedback(context)
  const blocked = review.controlMode === 'BLOCKED' || reality.metrics?.realtimeFeedback === 'BLOCKED'
  const restricted = review.controlMode === 'RESTRICTED' || context.feedback?.complianceRisk === 'HIGH'

  return {
    allowed: !blocked,
    level: blocked ? 'BLOCKED' : restricted ? 'RESTRICTED' : 'AUTO',
    controlMode: review.controlMode,
    reason: blocked
      ? 'business rule blocked by review or reality feedback'
      : restricted
        ? 'business rule requires human gate'
        : 'business rules passed',
  }
}

export function autoApplyCompliance(context = {}) {
  const rules = enforceBusinessRules(context)

  return {
    applied: rules.allowed,
    complianceMode: rules.level,
    actions: rules.allowed
      ? ['validate_policy_scope', 'sync_review_control', 'record_governance_decision']
      : ['halt_execution', 'notify_governance_owner'],
  }
}

export function overrideRiskyOperations(context = {}) {
  const riskLevel = context.decision?.risk?.level || context.riskLevel || 'LOW'
  const rules = enforceBusinessRules(context)
  const shouldOverride = rules.level === 'BLOCKED' || riskLevel === 'HIGH'

  return {
    override: shouldOverride,
    action: shouldOverride ? 'OVERRIDE_RISKY_OPERATION' : 'ALLOW_OPERATION',
    riskLevel,
    authority: 'AUTONOMOUS_GOVERNANCE',
  }
}

export function enforcePolicies(context = {}) {
  return {
    mode: 'V29_POLICY_ENFORCEMENT',
    businessRules: enforceBusinessRules(context),
    compliance: autoApplyCompliance(context),
    riskyOperationOverride: overrideRiskyOperations(context),
  }
}
