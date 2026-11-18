export const FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT_MODEL_VERSION = 'V1.14.2.8.6.14'

export const FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT = Object.freeze({
  contextCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT',
  version: FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT_MODEL_VERSION,
  contextKind: 'NON_EXECUTABLE_BOUNDARY_CONTEXT',
  fields: Object.freeze([
    'contextNo',
    'agreementNo',
    'environment',
    'contextMode',
    'requestedBy',
    'executorRoleId',
    'createdAt',
  ]),
  environment: 'isolated_design',
  contextMode: 'boundary_design_only',
  executable: false,
  productionCredentialsAvailable: false,
  productionEndpointConnected: false,
  workflowEngineConnected: false,
  persistenceAdapterConnected: false,
  contextInstanceCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalExecutionContext(model = FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT) {
  const valid = model.contextCode === 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT'
    && model.contextKind === 'NON_EXECUTABLE_BOUNDARY_CONTEXT'
    && model.environment === 'isolated_design'
    && model.contextMode === 'boundary_design_only'
    && model.executable === false
    && model.productionCredentialsAvailable === false
    && model.productionEndpointConnected === false
    && model.workflowEngineConnected === false
    && model.persistenceAdapterConnected === false
    && model.contextInstanceCount === 0
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
