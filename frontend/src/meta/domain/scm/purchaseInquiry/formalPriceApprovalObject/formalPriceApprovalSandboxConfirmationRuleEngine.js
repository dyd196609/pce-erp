export const FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_RULE_VERSION = 'V1.14.2.8.6.12'

export function evaluateFormalPriceApprovalCreationSandbox(input = {}) {
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'SANDBOX-001', pass: input.finalReleaseStatus === 'ready' }),
    Object.freeze({ ruleCode: 'SANDBOX-002', pass: input.environment === 'sandbox' }),
    Object.freeze({ ruleCode: 'SANDBOX-003', pass: input.productionEndpointConnected === false }),
    Object.freeze({ ruleCode: 'SANDBOX-004', pass: input.persistenceConnected === false }),
    Object.freeze({ ruleCode: 'SANDBOX-005', pass: input.workflowEngineConnected === false }),
  ])
  const passed = checks.every((item) => item.pass)
  return Object.freeze({
    result: passed ? 'PASS' : 'FAIL',
    decision: passed ? 'sandbox_validated' : 'blocked',
    readinessStatus: passed ? 'sandbox_ready' : 'blocked',
    evaluatedStatus: passed ? 'completed' : 'blocked',
    statusTrace: passed
      ? Object.freeze(['not_started', 'checking', 'sandbox_ready', 'completed'])
      : Object.freeze(['not_started', 'checking', 'blocked']),
    checks: Object.freeze(checks.map((item) => Object.freeze({ ruleCode: item.ruleCode, result: item.pass ? 'PASS' : 'FAIL' }))),
    environment: 'sandbox',
    productionEnvironmentUsed: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function evaluateFormalPriceApprovalHumanConfirmation(input = {}) {
  const confirmedBy = typeof input.confirmedBy === 'string' ? input.confirmedBy.trim() : ''
  const passed = input.sandboxStatus === 'completed'
    && input.confirmationMode === 'human'
    && confirmedBy.length > 0
  return Object.freeze({
    result: passed ? 'PASS' : 'FAIL',
    decision: passed ? 'confirmed_design_only' : 'rejected',
    evaluatedStatus: passed ? 'confirmed_design_only' : 'rejected',
    humanConfirmationRecognized: input.confirmationMode === 'human' && confirmedBy.length > 0,
    confirmationInstanceCreated: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
