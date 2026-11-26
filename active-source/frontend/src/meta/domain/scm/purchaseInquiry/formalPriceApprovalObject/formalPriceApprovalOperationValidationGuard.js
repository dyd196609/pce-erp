export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_GUARD_VERSION = 'V1.14.2.8.7.0'

export const FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_FORBIDDEN_ACTIONS = Object.freeze([
  'runProductionOperation', 'executeBusinessAction', 'createApprovalObject', 'startWorkflow',
  'createApprovalTask', 'persistValidationResult', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ productionOperation: false, businessExecution: false, approvalObjectCreated: false,
  workflowStarted: false, approvalTaskCreated: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalOperationValidationGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectBusinessValidationView') {
    const allowed = mode === 'validation_only'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_read_only' : 'deny', ...zeroEffect })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny',
    reason: protectedAction ? 'operation_validation_production_boundary_frozen' : 'operation_validation_default_deny', ...zeroEffect })
}
