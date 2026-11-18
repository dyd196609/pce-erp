export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_MODEL_VERSION = 'V1.14.2.8.6.10'

export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_STATES = Object.freeze([
  'not_requested',
  'pending_authorization',
  'authorized_design_only',
  'rejected',
])

export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION = Object.freeze({
  authorizationCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION',
  version: FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_MODEL_VERSION,
  authorizationKind: 'DESIGN_ONLY',
  fields: Object.freeze([
    'authorizationNo',
    'commandNo',
    'requesterId',
    'authorizerId',
    'requestedAt',
    'authorizedAt',
    'authorizationStatus',
    'decisionReason',
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_STATES,
  requesterAuthorizerSeparationRequired: true,
  executionPermissionGranted: false,
  authorizationInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCreationAuthorization(model = FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION) {
  const valid = model.authorizationCode === 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION'
    && model.authorizationKind === 'DESIGN_ONLY'
    && model.lifecycle.join(',') === 'not_requested,pending_authorization,authorized_design_only,rejected'
    && model.requesterAuthorizerSeparationRequired === true
    && model.executionPermissionGranted === false
    && model.authorizationInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
