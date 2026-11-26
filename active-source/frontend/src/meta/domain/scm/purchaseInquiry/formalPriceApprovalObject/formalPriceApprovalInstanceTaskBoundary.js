export const FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY_VERSION = 'V1.14.2.8.6.20'

export const FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY_VERSION,
  mode: 'definition_only',
  instanceDefinitionMeansCreated: false,
  taskDefinitionMeansCreated: false,
  workflowRunningMeansApprovalResult: false,
  instanceFactoryConnected: false,
  taskFactoryConnected: false,
  workflowEngineConnected: false,
  resultEngineConnected: false,
  persistenceAdapterConnected: false,
  productionExecution: false,
})

export function validateFormalPriceApprovalInstanceTaskBoundary(model = FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY) {
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY'
    && model.mode === 'definition_only'
    && model.instanceDefinitionMeansCreated === false
    && model.taskDefinitionMeansCreated === false
    && model.workflowRunningMeansApprovalResult === false
    && model.instanceFactoryConnected === false
    && model.taskFactoryConnected === false
    && model.workflowEngineConnected === false
    && model.resultEngineConnected === false
    && model.persistenceAdapterConnected === false
    && model.productionExecution === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
