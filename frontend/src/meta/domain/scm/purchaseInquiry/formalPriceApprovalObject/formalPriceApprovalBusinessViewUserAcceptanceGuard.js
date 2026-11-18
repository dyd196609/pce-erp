export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_GUARD_VERSION = 'V1.14.2.8.7.1'

export const FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_FORBIDDEN_ACTIONS = Object.freeze([
  'grantOperationApproval', 'runProductionOperation', 'executeBusinessAction', 'createApprovalObject',
  'startWorkflow', 'createApprovalTask', 'persistUserAcceptance', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ operationApprovalGranted: false, productionOperation: false, businessExecution: false,
  approvalObjectCreated: false, workflowStarted: false, approvalTaskCreated: false, persistencePerformed: false,
  businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalBusinessViewUserAcceptanceGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectUserAcceptancePreparation') {
    const allowed = mode === 'read_only_walkthrough'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_read_only' : 'deny', ...zeroEffect })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny',
    reason: protectedAction ? 'user_acceptance_execution_boundary_frozen' : 'user_acceptance_default_deny', ...zeroEffect })
}
