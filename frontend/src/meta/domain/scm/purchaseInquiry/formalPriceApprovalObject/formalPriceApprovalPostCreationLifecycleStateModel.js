export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MODEL_VERSION = 'V1.14.2.8.6.17'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATES = Object.freeze([
  Object.freeze({ code: 'created', terminal: false, mutationAllowed: false }),
  Object.freeze({ code: 'pending_approval', terminal: false, mutationAllowed: false }),
  Object.freeze({ code: 'approved', terminal: true, mutationAllowed: false }),
  Object.freeze({ code: 'rejected', terminal: true, mutationAllowed: false }),
  Object.freeze({ code: 'cancelled', terminal: true, mutationAllowed: false }),
])

export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE = Object.freeze({
  stateMachineCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE',
  version: FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MODEL_VERSION,
  lifecycle: Object.freeze(FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATES.map((item) => item.code)),
  executionMode: 'frozen_design_only',
  automaticProgression: false,
  stateMutationAllowed: false,
  workflowEngineConnected: false,
  persistenceAdapterConnected: false,
  stateMachineInstanceCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalPostCreationLifecycleStateModel(model = FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE) {
  const valid = model.stateMachineCode === 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE'
    && model.lifecycle.join(',') === 'created,pending_approval,approved,rejected,cancelled'
    && FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATES.every((item) => item.mutationAllowed === false)
    && model.executionMode === 'frozen_design_only'
    && model.automaticProgression === false
    && model.stateMutationAllowed === false
    && model.workflowEngineConnected === false
    && model.persistenceAdapterConnected === false
    && model.stateMachineInstanceCount === 0
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
