export const FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_VERSION = 'V1.14.2.8.6.20'

export const FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE = Object.freeze({
  lifecycleCode: 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE',
  version: FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_VERSION,
  states: Object.freeze(['definition_only', 'ready_for_creation', 'created', 'running', 'completed', 'cancelled']),
  currentState: 'definition_only',
  allowedCurrentStates: Object.freeze(['definition_only', 'ready_for_creation']),
  definitionMeansCreated: false,
  automaticProgression: false,
  enabledTransitionCount: 0,
  instanceCount: 0,
  persistenceConnected: false,
})

export function validateFormalPriceApprovalInstanceLifecycle(model = FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE) {
  const valid = model.lifecycleCode === 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE'
    && model.states.join(',') === 'definition_only,ready_for_creation,created,running,completed,cancelled'
    && model.allowedCurrentStates.join(',') === 'definition_only,ready_for_creation'
    && model.allowedCurrentStates.includes(model.currentState)
    && model.definitionMeansCreated === false
    && model.automaticProgression === false
    && model.enabledTransitionCount === 0
    && model.instanceCount === 0
    && model.persistenceConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
