export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_GUARD_VERSION = 'V1.14.2.8.6.13'

export const FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_FORBIDDEN_ACTIONS = Object.freeze([
  'autoAgree',
  'executeAgreement',
  'grantExecutionPermission',
  'executeCommand',
  'dispatchCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'createApprovalTask',
  'persistAgreement',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalFinalReleaseAgreementGuard({ action = '', requesterId = '', reviewerId = '', executorRoleId = '', reviewMode = '' } = {}) {
  if (action === 'reviewAgreement') {
    const separated = Boolean(requesterId) && Boolean(reviewerId) && Boolean(executorRoleId)
      && requesterId !== reviewerId && reviewerId !== executorRoleId
    const allowed = separated && reviewMode === 'human'
    return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', decision: allowed ? 'allow_agreement_review_only' : 'deny', executionPermissionGranted: false, commandExecuted: false, formalPriceApprovalObjectCreated: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'agreement_is_not_execution' : 'agreement_default_deny',
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
