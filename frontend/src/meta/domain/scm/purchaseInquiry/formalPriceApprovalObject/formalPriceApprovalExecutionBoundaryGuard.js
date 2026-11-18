export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_GUARD_VERSION = 'V1.14.2.8.6.14'

export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_FORBIDDEN_ACTIONS = Object.freeze([
  'autoExecuteApprovedAgreement',
  'executeBoundary',
  'connectExecutor',
  'enableProductionExecution',
  'loadProductionCredentials',
  'executeCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'persistExecutionContext',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalExecutionBoundaryGuard({ action = '', environment = '', contextMode = '' } = {}) {
  if (action === 'evaluateBoundary') {
    const isolated = environment === 'isolated_design' && contextMode === 'boundary_design_only'
    return Object.freeze({ result: isolated ? 'PASS' : 'FAIL', decision: isolated ? 'allow_boundary_evaluation_only' : 'deny', boundaryIsExecutor: false, executionPermissionGranted: false, productionExecution: false, commandExecuted: false, formalPriceApprovalObjectCreated: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'execution_boundary_is_not_executor' : 'execution_boundary_default_deny',
    boundaryIsExecutor: false,
    executionPermissionGranted: false,
    productionExecution: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
