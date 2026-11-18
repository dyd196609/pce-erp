export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_VERSION = 'V1.14.2.8.6.10'

export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_AUTHORIZATION_AUDIT_READY',
  route: '/scm/purchase-inquiry',
  authorizationCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION',
  auditCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL',
  requiredRegions: Object.freeze(['formal-price-approval-creation-authorization-audit']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  requesterAuthorizerSeparationRequired: true,
  authorizationIsExecution: false,
  auditIsPersistence: false,
  authorizationInstanceCreated: false,
  auditRecordWritten: false,
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCreationAuthorizationAuditAcceptance(profile = FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.requesterAuthorizerSeparationRequired === true
    && profile.authorizationIsExecution === false
    && profile.auditIsPersistence === false
    && profile.authorizationInstanceCreated === false
    && profile.auditRecordWritten === false
    && profile.formalPriceApprovalObjectCreated === false
    && profile.approvalWorkflowStarted === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
