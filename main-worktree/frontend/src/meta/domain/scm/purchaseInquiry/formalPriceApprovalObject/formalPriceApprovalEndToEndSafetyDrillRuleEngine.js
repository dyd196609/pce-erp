import { buildFormalPriceApprovalEndToEndSafetyDrillMatrix } from './formalPriceApprovalEndToEndSafetyDrillMatrix.js'

export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_RULE_VERSION = 'V1.14.2.8.6.15'

export function evaluateFormalPriceApprovalEndToEndSafetyDrill(input = {}) {
  if (input.drillRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_started', evaluatedStatus: 'not_started', statusTrace: Object.freeze(['not_started']), drillIsExecution: false, simulationIsCreation: false, boundaryIsExecutor: false, productionExecution: false, commandExecuted: false, formalPriceApprovalObjectCreated: false, approvalWorkflowStarted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const matrix = buildFormalPriceApprovalEndToEndSafetyDrillMatrix(input.stageResults)
  const safetyViolation = input.productionExecution === true
    || input.commandExecuted === true
    || input.formalPriceApprovalObjectCreated === true
    || input.approvalWorkflowStarted === true
    || Number(input.businessWriteCount || 0) > 0
    || matrix.failedCount > 0
  const evaluatedStatus = safetyViolation ? 'blocked' : (matrix.complete ? 'completed' : 'manual_review')
  return Object.freeze({
    result: evaluatedStatus === 'blocked' ? 'FAIL' : 'PASS',
    decision: evaluatedStatus,
    evaluatedStatus,
    statusTrace: Object.freeze(['not_started', 'checking', evaluatedStatus]),
    matrix,
    drillIsExecution: false,
    simulationIsCreation: false,
    boundaryIsExecutor: false,
    productionExecution: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
