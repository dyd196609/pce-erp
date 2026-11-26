export const FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY_VERSION = 'V1.14.2.8.6.21'

export const FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY_VERSION,
  mode: 'result_isolated_definition_only',
  runtimeArtifactType: 'workflow_runtime_state',
  resultArtifactType: 'approval_result',
  businessStateArtifactType: 'formal_price_approval_business_state',
  workflowRunningMeansApproved: false,
  workflowCompletedMeansResultCreated: false,
  runtimeStateMeansBusinessState: false,
  resultFactoryConnected: false,
  businessStateManagerConnected: false,
  persistenceAdapterConnected: false,
  resultCount: 0,
  productionExecution: false,
})

export function validateFormalPriceApprovalResultBoundary(model = FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY) {
  const artifactTypes = [model.runtimeArtifactType, model.resultArtifactType, model.businessStateArtifactType]
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY'
    && model.mode === 'result_isolated_definition_only'
    && new Set(artifactTypes).size === 3
    && model.workflowRunningMeansApproved === false
    && model.workflowCompletedMeansResultCreated === false
    && model.runtimeStateMeansBusinessState === false
    && model.resultFactoryConnected === false
    && model.businessStateManagerConnected === false
    && model.persistenceAdapterConnected === false
    && model.resultCount === 0
    && model.productionExecution === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
