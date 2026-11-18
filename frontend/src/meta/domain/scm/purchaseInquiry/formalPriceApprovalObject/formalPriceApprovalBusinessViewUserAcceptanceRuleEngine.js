export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_RULE_VERSION = 'V1.14.2.8.7.1'

export function evaluateFormalPriceApprovalBusinessViewUserAcceptance(input = {}) {
  if (input.preparationRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_prepared', preparationStatus: 'not_prepared', operationApprovalGranted: false, productionOperation: false, businessExecution: false, approvalObjectCreated: false, workflowStarted: false, approvalTaskCreated: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const prepared = input.operationValidationStatus === 'validation_ready'
    && input.businessViewOptimizationStatus === 'user_acceptance_ready'
    && Number(input.passedChecklistCount) === 5 && input.serverFactsConfirmed === true && input.zeroWriteConfirmed === true
  const forbiddenRequest = input.operationApprovalRequested === true || input.productionOperationRequested === true
    || input.businessExecutionRequested === true || input.approvalObjectCreationRequested === true
    || input.workflowStartRequested === true || input.approvalTaskCreationRequested === true
    || input.persistenceRequested === true || Number(input.businessWriteCount || 0) > 0
  const preparationStatus = prepared && !forbiddenRequest ? 'ready_for_user_acceptance' : 'blocked'
  return Object.freeze({ result: preparationStatus === 'ready_for_user_acceptance' ? 'PASS' : 'FAIL', decision: preparationStatus, preparationStatus,
    businessViewMeansBusinessExecution: false, userAcceptanceMeansOperationApproval: false,
    operationApprovalGranted: false, productionOperation: false, businessExecution: false,
    approvalObjectCreated: false, workflowStarted: false, approvalTaskCreated: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
}
