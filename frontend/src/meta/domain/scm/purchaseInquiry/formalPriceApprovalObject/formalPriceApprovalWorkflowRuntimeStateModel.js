export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE_VERSION = 'V1.14.2.8.6.21'

export const FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE = Object.freeze({
  runtimeStateCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE',
  version: FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE_VERSION,
  states: Object.freeze(['definition_only', 'ready_for_runtime', 'initialized', 'running', 'completed', 'failed', 'cancelled']),
  currentState: 'definition_only',
  allowedCurrentStates: Object.freeze(['definition_only', 'ready_for_runtime']),
  runtimeStateMeansBusinessState: false,
  runningMeansApproved: false,
  completedMeansResultCreated: false,
  automaticProgression: false,
  enabledTransitionCount: 0,
  runtimeInstanceCount: 0,
  persistenceConnected: false,
})

export function validateFormalPriceApprovalWorkflowRuntimeState(model = FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE) {
  const valid = model.runtimeStateCode === 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE'
    && model.states.join(',') === 'definition_only,ready_for_runtime,initialized,running,completed,failed,cancelled'
    && model.allowedCurrentStates.join(',') === 'definition_only,ready_for_runtime'
    && model.allowedCurrentStates.includes(model.currentState)
    && model.runtimeStateMeansBusinessState === false
    && model.runningMeansApproved === false
    && model.completedMeansResultCreated === false
    && model.automaticProgression === false
    && model.enabledTransitionCount === 0
    && model.runtimeInstanceCount === 0
    && model.persistenceConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
