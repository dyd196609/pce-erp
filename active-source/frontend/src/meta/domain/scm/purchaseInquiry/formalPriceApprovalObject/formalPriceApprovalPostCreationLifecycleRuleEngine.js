import { inspectFormalPriceApprovalPostCreationLifecycleTransition } from './formalPriceApprovalPostCreationLifecycleTransitionMatrix.js'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_RULE_VERSION = 'V1.14.2.8.6.17'

export function evaluateFormalPriceApprovalPostCreationLifecycle(input = {}) {
  if (input.transitionAssessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', evaluatedStatus: 'not_assessed', currentState: input.fromState || 'created', stateChanged: false, lifecycleExecuted: false, workflowEngineConnected: false, statePersisted: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const transition = inspectFormalPriceApprovalPostCreationLifecycleTransition({ fromState: input.fromState, toState: input.toState })
  const safetyViolation = input.automaticTransition === true
    || input.workflowEngineConnected === true
    || input.statePersistenceConnected === true
    || input.lifecycleExecutionRequested === true
    || input.formalPriceApprovalObjectCreatedNow === true
    || Number(input.businessWriteCount || 0) > 0
  const evaluatedStatus = safetyViolation || !transition.defined ? 'blocked' : 'transition_defined_frozen'
  return Object.freeze({
    result: evaluatedStatus === 'blocked' ? 'FAIL' : 'PASS',
    decision: evaluatedStatus,
    evaluatedStatus,
    transition,
    currentState: input.fromState,
    evaluatedTargetState: input.toState,
    stateChanged: false,
    lifecycleExecuted: false,
    automaticTransition: false,
    workflowEngineConnected: false,
    statePersisted: false,
    formalPriceApprovalObjectCreatedNow: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
