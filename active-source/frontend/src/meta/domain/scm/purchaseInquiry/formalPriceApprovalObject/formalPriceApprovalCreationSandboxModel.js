export const FORMAL_PRICE_APPROVAL_CREATION_SANDBOX_MODEL_VERSION = 'V1.14.2.8.6.12'

export const FORMAL_PRICE_APPROVAL_CREATION_SANDBOX_STATES = Object.freeze([
  'not_started',
  'checking',
  'sandbox_ready',
  'blocked',
  'completed',
])

export const FORMAL_PRICE_APPROVAL_CREATION_SANDBOX = Object.freeze({
  sandboxCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SANDBOX',
  version: FORMAL_PRICE_APPROVAL_CREATION_SANDBOX_MODEL_VERSION,
  artifactType: 'NON_PRODUCTION_SANDBOX_VALIDATION',
  environment: 'sandbox',
  fields: Object.freeze([
    'sandboxNo',
    'inquiryNo',
    'finalReleaseAssessmentNo',
    'sandboxStatus',
    'validationResults',
    'blockedReasons',
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_CREATION_SANDBOX_STATES,
  productionEndpointConnected: false,
  persistenceMode: 'none',
  formalPriceApprovalObjectCreated: false,
  sandboxInstanceCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCreationSandbox(model = FORMAL_PRICE_APPROVAL_CREATION_SANDBOX) {
  const valid = model.sandboxCode === 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SANDBOX'
    && model.artifactType === 'NON_PRODUCTION_SANDBOX_VALIDATION'
    && model.environment === 'sandbox'
    && model.lifecycle.join(',') === 'not_started,checking,sandbox_ready,blocked,completed'
    && model.productionEndpointConnected === false
    && model.persistenceMode === 'none'
    && model.formalPriceApprovalObjectCreated === false
    && model.sandboxInstanceCount === 0
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
