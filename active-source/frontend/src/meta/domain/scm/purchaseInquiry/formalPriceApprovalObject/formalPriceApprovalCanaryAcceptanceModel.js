export const FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_VERSION = 'V1.14.2.8.7.6'

export const FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_VERSION,
  canaryNo: 'FPA-CANARY-DEFINITION-001',
  environment: 'canary',
  scope: 'page_view_and_human_understanding_only',
  scenarioSource: 'synthetic',
  status: 'ready_for_human_acceptance',
  productionConnected: false,
  isProduction: false,
  createsBusinessObject: false,
  createsApprovalObject: false,
  startsWorkflow: false,
  persisted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCanaryAcceptance(model = FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE'
    && model.environment === 'canary' && model.scenarioSource === 'synthetic'
    && model.status === 'ready_for_human_acceptance'
    && model.productionConnected === false && model.isProduction === false
    && model.createsBusinessObject === false && model.createsApprovalObject === false
    && model.startsWorkflow === false && model.persisted === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
