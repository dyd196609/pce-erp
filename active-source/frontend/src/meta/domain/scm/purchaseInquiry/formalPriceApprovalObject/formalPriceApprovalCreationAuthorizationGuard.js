export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_GUARD_VERSION = 'V1.14.2.8.6.10'

export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_FORBIDDEN_ACTIONS = Object.freeze([
  'autoAuthorize',
  'grantExecutionPermission',
  'executeAuthorization',
  'executeCommand',
  'createFormalPriceApprovalObject',
  'startApprovalWorkflow',
  'createApprovalTask',
  'persistAuthorization',
  'persistAuditTrail',
  'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalCreationAuthorizationGuard({ action = '', requesterId = '', authorizerId = '' } = {}) {
  if (action === 'reviewAuthorization') {
    const separated = Boolean(requesterId) && Boolean(authorizerId) && requesterId !== authorizerId
    return Object.freeze({
      result: separated ? 'PASS' : 'FAIL',
      decision: separated ? 'allow_design_review' : 'deny',
      reason: separated ? '' : 'requester_authorizer_must_be_different',
      executionPermissionGranted: false,
      businessWriteCount: 0,
      productionDataWritten: false,
    })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({
    result: protectedAction ? 'PASS' : 'FAIL',
    decision: 'deny',
    reason: protectedAction ? 'authorization_execution_and_persistence_frozen' : 'authorization_default_deny',
    executionPermissionGranted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
