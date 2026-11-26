export const FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_GUARD_VERSION = 'V1.14.2.8.7.4'

export const FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_FORBIDDEN_ACTIONS = Object.freeze([
  'triggerBusinessActionFromViewSwitch', 'createApprovalObject', 'startWorkflow',
  'deleteHiddenGovernanceModel', 'persistViewMode', 'writeProductionDatabase',
])

const zeroEffect = Object.freeze({ businessActionTriggered: false, approvalObjectCreated: false, workflowStarted: false,
  governanceModelDeleted: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalViewSeparationGuard({ action = '', targetMode = '' } = {}) {
  if (action === 'switchViewMode') {
    const allowed = ['business_view', 'acceptance_view'].includes(targetMode)
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_presentation_only' : 'deny', ...zeroEffect })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny',
    reason: protectedAction ? 'view_separation_business_boundary_frozen' : 'view_separation_default_deny', ...zeroEffect })
}
