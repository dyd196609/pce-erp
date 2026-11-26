import { FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE } from './formalPriceApprovalObjectStateModel.js'

export const FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE_VERSION = 'V1.14.2.8.6.7'

export const FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS = Object.freeze([
  Object.freeze({ from: 'definition_only', to: 'ready_for_creation', enabled: true, mode: 'design_evaluation_only' }),
  Object.freeze({ from: 'ready_for_creation', to: 'created', enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'created', to: 'pending_approval', enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'pending_approval', to: 'approved', enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'pending_approval', to: 'rejected', enabled: false, mode: 'frozen' }),
  Object.freeze({ from: 'created', to: 'cancelled', enabled: false, mode: 'frozen' }),
])

export const FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE = Object.freeze({
  machineCode: 'SCM_FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE',
  version: FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE_VERSION,
  lifecycle: FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE,
  transitions: FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS,
  transitionMode: 'design_evaluation_only',
  stateMutationAllowed: false,
  automaticProgression: false,
  workflowEngineConnected: false,
})

export function evaluateFormalPriceApprovalRuntimeTransition({ fromStatus, toStatus } = {}) {
  if (!FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE.includes(fromStatus) || !FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE.includes(toStatus)) {
    return Object.freeze({ result: 'UNKNOWN', decision: 'deny', reason: 'runtime_state_unknown', stateChanged: false })
  }
  const transition = FORMAL_PRICE_APPROVAL_RUNTIME_TRANSITIONS.find((item) => item.from === fromStatus && item.to === toStatus)
  const allowedDesignTransition = transition?.enabled === true
  return Object.freeze({
    result: allowedDesignTransition ? 'PASS' : 'FAIL',
    decision: allowedDesignTransition ? 'allow_design_evaluation' : 'deny',
    reason: allowedDesignTransition ? '' : 'runtime_transition_frozen',
    fromStatus,
    evaluatedTargetStatus: toStatus,
    currentStatus: fromStatus,
    stateChanged: false,
    stateMutationAllowed: false,
  })
}
