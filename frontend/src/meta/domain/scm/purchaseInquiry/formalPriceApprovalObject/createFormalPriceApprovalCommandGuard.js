export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_GUARD_VERSION = 'V1.14.2.8.6.9'

export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_FORBIDDEN_ACTIONS = Object.freeze([
  'autoTriggerCommand',
  'autoSubmitCommand',
  'approveForExecution',
  'executeCommand',
  'dispatchCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'createApprovalInstance',
  'createApprovalTask',
  'writeProductionDatabase',
])

export function evaluateCreateFormalPriceApprovalCommandGuard(action = '') {
  const protectedAction = CREATE_FORMAL_PRICE_APPROVAL_COMMAND_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'formal_price_approval_command_execution_frozen' : 'command_design_default_deny',
    approvedForExecution: false,
    executed: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
