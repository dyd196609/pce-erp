export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX_VERSION = 'V1.14.2.8.6.11'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX = Object.freeze([
  Object.freeze({ controlCode: 'FINAL-RELEASE-001', evidence: 'simulationStatus', expected: 'completed' }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-002', evidence: 'commandStatus', expected: 'validated' }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-003', evidence: 'authorizationStatus', expected: 'authorized_design_only' }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-004', evidence: 'requesterAuthorizerSeparated', expected: true }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-005', evidence: 'auditTrailAvailable', expected: true }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-006', evidence: 'workflowEngineConnected', expected: false }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-007', evidence: 'commandExecuted', expected: false }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-008', evidence: 'formalPriceApprovalObjectCreated', expected: false }),
  Object.freeze({ controlCode: 'FINAL-RELEASE-009', evidence: 'businessWriteCount', expected: 0 }),
])

export function evaluateFormalPriceApprovalFinalReleaseMatrix(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({
      result: 'PASS',
      decision: 'not_assessed',
      evaluatedStatus: 'not_assessed',
      statusTrace: Object.freeze(['not_assessed']),
      findings: Object.freeze([]),
      releaseIsExecution: false,
      readyMeansCreated: false,
      commandExecuted: false,
      formalPriceApprovalObjectCreated: false,
      approvalWorkflowStarted: false,
      businessWriteCount: 0,
      productionDataWritten: false,
    })
  }
  const findings = Object.freeze(FORMAL_PRICE_APPROVAL_FINAL_RELEASE_MATRIX.map((control) => Object.freeze({
    controlCode: control.controlCode,
    result: input[control.evidence] === control.expected ? 'PASS' : 'FAIL',
  })))
  const safetyViolation = input.requesterAuthorizerSeparated === false
    || input.workflowEngineConnected === true
    || input.commandExecuted === true
    || input.formalPriceApprovalObjectCreated === true
    || Number(input.businessWriteCount || 0) > 0
  const evidenceComplete = findings.every((item) => item.result === 'PASS')
  const evaluatedStatus = safetyViolation ? 'blocked' : (evidenceComplete ? 'ready' : 'manual_review')
  return Object.freeze({
    result: evaluatedStatus === 'blocked' ? 'FAIL' : 'PASS',
    decision: evaluatedStatus,
    evaluatedStatus,
    statusTrace: Object.freeze(['not_assessed', 'checking', evaluatedStatus]),
    findings,
    releaseIsExecution: false,
    readyMeansCreated: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
