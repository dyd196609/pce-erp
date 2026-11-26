export const FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE_VERSION = 'V1.14.2.8.6.20'

export const FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE = Object.freeze({
  lifecycleCode: 'SCM_FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE',
  version: FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE_VERSION,
  states: Object.freeze(['definition_only', 'ready_for_creation', 'created', 'pending', 'approved', 'rejected', 'cancelled']),
  currentState: 'definition_only',
  allowedCurrentStates: Object.freeze(['definition_only', 'ready_for_creation']),
  definitionMeansCreated: false,
  workflowRunningMeansApprovalResult: false,
  automaticProgression: false,
  enabledTransitionCount: 0,
  taskCount: 0,
  persistenceConnected: false,
})

export function validateFormalPriceApprovalTaskLifecycle(model = FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE) {
  const valid = model.lifecycleCode === 'SCM_FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE'
    && model.states.join(',') === 'definition_only,ready_for_creation,created,pending,approved,rejected,cancelled'
    && model.allowedCurrentStates.join(',') === 'definition_only,ready_for_creation'
    && model.allowedCurrentStates.includes(model.currentState)
    && model.definitionMeansCreated === false
    && model.workflowRunningMeansApprovalResult === false
    && model.automaticProgression === false
    && model.enabledTransitionCount === 0
    && model.taskCount === 0
    && model.persistenceConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
