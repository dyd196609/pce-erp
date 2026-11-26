export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_RULE_VERSION = 'V1.14.2.8.7.0'

export function evaluateFormalPriceApprovalOperationValidation(input = {}) {
  if (input.validationRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_started', validationStatus: 'not_started', productionOperation: false, businessExecution: false, approvalObjectCreated: false, workflowStarted: false, approvalTaskCreated: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const evidenceReady = input.governanceSummaryStatus === 'validation_ready'
    && Number(input.scenarioCount) === 4 && input.serverFactsConfirmed === true && input.zeroWriteConfirmed === true
  const forbiddenRequest = input.productionOperationRequested === true || input.businessExecutionRequested === true
    || input.approvalObjectCreationRequested === true || input.workflowStartRequested === true
    || input.approvalTaskCreationRequested === true || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const validationStatus = evidenceReady && !forbiddenRequest ? 'validation_ready' : 'blocked'
  return Object.freeze({ result: validationStatus === 'validation_ready' ? 'PASS' : 'FAIL', decision: validationStatus, validationStatus,
    operationValidationMeansProductionOperation: false, businessViewMeansBusinessExecution: false,
    productionOperation: false, businessExecution: false, approvalObjectCreated: false, workflowStarted: false,
    approvalTaskCreated: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}
