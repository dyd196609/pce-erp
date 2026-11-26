export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_GATE_VERSION = 'V1.14.2.8.6.11'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_FORBIDDEN_ACTIONS = Object.freeze([
  'executeFinalRelease',
  'grantExecutionPermission',
  'executeCommand',
  'dispatchCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'createApprovalInstance',
  'createApprovalTask',
  'persistFinalReleaseAssessment',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalFinalReleaseGate({ action = '', assessmentStatus = 'not_assessed' } = {}) {
  if (action === 'reviewFinalRelease') {
    return Object.freeze({
      result: 'PASS',
      decision: 'allow_assessment_only',
      assessmentStatus,
      executionPermissionGranted: false,
      commandExecuted: false,
      formalPriceApprovalObjectCreated: false,
      businessWriteCount: 0,
      productionDataWritten: false,
    })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_FINAL_RELEASE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'final_release_is_not_execution' : 'final_release_gate_default_deny',
    assessmentStatus,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
