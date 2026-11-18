export const FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION_RULE_VERSION = 'V1.14.2.8.7.2'

export function evaluateFormalPriceApprovalBusinessNavigation(input = {}) {
  if (input.validationRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_validated', navigationStatus: 'not_validated', routeActionPerformed: false, workflowRuntimeStarted: false, autoActionPerformed: false, approvalObjectCreated: false, approvalTaskCreated: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const pathReady = input.userAcceptanceStatus === 'ready_for_user_acceptance'
    && Number(input.stepCount) === 5 && Number(input.roleCount) === 3
    && input.pathLabelsConfirmed === true && input.zeroWriteConfirmed === true
  const forbiddenRequest = input.routeActionRequested === true || input.workflowRuntimeRequested === true
    || input.autoActionRequested === true || input.approvalObjectCreationRequested === true
    || input.approvalTaskCreationRequested === true || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  const navigationStatus = pathReady && !forbiddenRequest ? 'ready_for_user_path_validation' : 'blocked'
  return Object.freeze({ result: navigationStatus === 'ready_for_user_path_validation' ? 'PASS' : 'FAIL', decision: navigationStatus, navigationStatus,
    navigationMeansExecution: false, userPathMeansWorkflowRuntime: false, nextStepMeansAutoAction: false,
    routeActionPerformed: false, workflowRuntimeStarted: false, autoActionPerformed: false,
    approvalObjectCreated: false, approvalTaskCreated: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false })
}
