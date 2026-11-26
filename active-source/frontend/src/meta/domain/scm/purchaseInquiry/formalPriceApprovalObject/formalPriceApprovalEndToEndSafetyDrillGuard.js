export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_GUARD_VERSION = 'V1.14.2.8.6.15'

export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_FORBIDDEN_ACTIONS = Object.freeze([
  'runDrillInProduction',
  'executeDrill',
  'grantExecutionPermission',
  'executeCommand',
  'dispatchCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'connectExecutor',
  'persistDrillResult',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalEndToEndSafetyDrillGuard({ action = '', executionMode = '' } = {}) {
  if (action === 'runSafetyDrill') {
    const isolated = executionMode === 'isolated_read_only'
    return Object.freeze({ result: isolated ? 'PASS' : 'FAIL', decision: isolated ? 'allow_read_only_drill' : 'deny', drillIsExecution: false, executionPermissionGranted: false, productionExecution: false, commandExecuted: false, formalPriceApprovalObjectCreated: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'safety_drill_is_not_execution' : 'safety_drill_default_deny',
    drillIsExecution: false,
    executionPermissionGranted: false,
    productionExecution: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
