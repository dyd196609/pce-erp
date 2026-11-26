export const FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY_VERSION = 'V1.14.2.8.6.19'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY_VERSION,
  boundaryMode: 'isolated_definition_only',
  requestArtifactType: 'start_assessment_evidence',
  instanceArtifactType: 'workflow_instance',
  requestSeparatedFromInstance: true,
  instanceFactoryConnected: false,
  workflowEngineConnected: false,
  approvalTaskFactoryConnected: false,
  persistenceAdapterConnected: false,
  instanceCreationAllowed: false,
  productionExecutionAllowed: false,
})

export function validateFormalPriceApprovalWorkflowInstanceBoundary(model = FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY) {
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY'
    && model.boundaryMode === 'isolated_definition_only'
    && model.requestArtifactType !== model.instanceArtifactType
    && model.requestSeparatedFromInstance === true
    && model.instanceFactoryConnected === false
    && model.workflowEngineConnected === false
    && model.approvalTaskFactoryConnected === false
    && model.persistenceAdapterConnected === false
    && model.instanceCreationAllowed === false
    && model.productionExecutionAllowed === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
