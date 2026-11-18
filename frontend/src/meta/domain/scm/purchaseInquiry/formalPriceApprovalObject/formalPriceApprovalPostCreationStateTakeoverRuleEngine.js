export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_RULE_VERSION = 'V1.14.2.8.6.16'

export function evaluateFormalPriceApprovalPostCreationStateTakeover(input = {}) {
  if (input.takeoverAssessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', evaluatedStatus: 'not_assessed', currentState: 'created', evaluatedTargetState: 'pending_approval', stateChanged: false, automaticTakeover: false, workflowEngineConnected: false, approvalWorkflowStarted: false, approvalTaskCreated: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'POST-CREATION-001', pass: input.creationEvidenceStatus === 'verified_future_evidence' }),
    Object.freeze({ ruleCode: 'POST-CREATION-002', pass: input.currentState === 'created' }),
    Object.freeze({ ruleCode: 'POST-CREATION-003', pass: input.takeoverMode === 'manual_isolated' }),
    Object.freeze({ ruleCode: 'POST-CREATION-004', pass: input.stateOwnershipVerified === true }),
    Object.freeze({ ruleCode: 'POST-CREATION-005', pass: input.workflowEngineConnected === false }),
    Object.freeze({ ruleCode: 'POST-CREATION-006', pass: input.stateMutationAllowed === false }),
  ])
  const safetyViolation = input.workflowEngineConnected === true
    || input.stateMutationAllowed === true
    || input.automaticTakeover === true
    || input.autoTransitionToPendingApproval === true
    || input.formalPriceApprovalObjectCreatedNow === true
    || Number(input.businessWriteCount || 0) > 0
  const complete = checks.every((item) => item.pass)
  const evaluatedStatus = safetyViolation ? 'blocked' : (complete ? 'takeover_ready' : (input.creationEvidenceStatus ? 'manual_review' : 'awaiting_created_evidence'))
  return Object.freeze({
    result: evaluatedStatus === 'blocked' ? 'FAIL' : 'PASS',
    decision: evaluatedStatus,
    evaluatedStatus,
    checks: Object.freeze(checks.map((item) => Object.freeze({ ruleCode: item.ruleCode, result: item.pass ? 'PASS' : 'FAIL' }))),
    currentState: 'created',
    evaluatedTargetState: 'pending_approval',
    stateChanged: false,
    stateMutationAllowed: false,
    automaticTakeover: false,
    workflowEngineConnected: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    formalPriceApprovalObjectCreatedNow: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
