export const FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_GUARD_VERSION = 'V1.14.2.8.6.12'

export const FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_FORBIDDEN_ACTIONS = Object.freeze([
  'runInProduction',
  'connectProductionEndpoint',
  'autoConfirm',
  'executeConfirmation',
  'grantExecutionPermission',
  'executeCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'persistSandboxResult',
  'persistHumanConfirmation',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalSandboxConfirmationGuard({ action = '', environment = '', confirmationMode = '' } = {}) {
  if (action === 'runSandboxValidation') {
    const sandboxOnly = environment === 'sandbox'
    return Object.freeze({ result: sandboxOnly ? 'PASS' : 'FAIL', decision: sandboxOnly ? 'allow_sandbox_validation_only' : 'deny', executionPermissionGranted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  if (action === 'reviewHumanConfirmation') {
    const humanOnly = confirmationMode === 'human'
    return Object.freeze({ result: humanOnly ? 'PASS' : 'FAIL', decision: humanOnly ? 'allow_confirmation_review_only' : 'deny', executionPermissionGranted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_SANDBOX_CONFIRMATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'sandbox_confirmation_execution_frozen' : 'sandbox_confirmation_default_deny',
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
