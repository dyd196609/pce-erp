export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_GUARD_VERSION = 'V1.14.2.8.7.6.1'

export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_FORBIDDEN_ACTIONS = Object.freeze([
  'runAgainstProduction', 'persistAutomaticAcceptanceResult', 'createBusinessObjectFromCanaryResult',
  'createApprovalObjectFromCanaryResult', 'startWorkflowFromCanaryResult', 'createApprovalTaskFromCanaryResult',
  'updateFeedbackLoopAutomatically', 'changeBusinessStateFromCanaryResult', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ businessExecutionTriggered: false, feedbackLoopUpdated: false,
  resultPersisted: false, businessObjectCreated: false, approvalObjectCreated: false,
  workflowStarted: false, approvalTaskCreated: false, businessStateChanged: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalCanaryCohortGuard({ action = '', environment = '' } = {}) {
  if (action === 'runInMemoryCanaryCohort') {
    const allowed = environment === 'canary'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_validation_only' : 'deny', ...zeroEffect })
  }
  const forbidden = FORMAL_PRICE_APPROVAL_CANARY_COHORT_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', decision: 'deny',
    reason: forbidden ? 'canary_cohort_business_effect_frozen' : 'canary_cohort_default_deny', ...zeroEffect })
}
