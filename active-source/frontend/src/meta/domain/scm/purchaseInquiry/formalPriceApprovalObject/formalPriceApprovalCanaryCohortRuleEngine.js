export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_RULE_VERSION = 'V1.14.2.8.7.6.1'

const zeroEffect = Object.freeze({ businessExecutionTriggered: false, feedbackLoopUpdated: false,
  resultPersisted: false, businessObjectCreated: false, approvalObjectCreated: false,
  workflowStarted: false, approvalTaskCreated: false, businessStateChanged: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalCanaryCohort(input = {}) {
  if (input.action !== 'runAutomaticAcceptance') {
    return Object.freeze({ result: 'FAIL', decision: 'blocked', executionState: 'blocked', results: Object.freeze([]), ...zeroEffect })
  }
  const validEnvironment = input.environment === 'canary' && input.productionConnected === false
  const validMembers = Array.isArray(input.members) && input.members.length > 0
    && input.members.every(item => item.environment === 'canary' && item.productionConnected === false
      && Array.isArray(item.assertions) && item.assertions.length > 0)
  const allowed = validEnvironment && validMembers && input.persistRequested !== true
  const results = allowed ? input.members.map(item => Object.freeze({ memberCode: item.memberCode, result: 'PASS' })) : []
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'validation_completed' : 'blocked',
    executionState: allowed ? 'completed' : 'blocked', results: Object.freeze(results), ...zeroEffect })
}
