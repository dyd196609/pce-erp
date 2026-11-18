export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP_VERSION = 'V1.14.2.8.7.6'

export const FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP',
  version: FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP_VERSION,
  states: Object.freeze(['not_recorded', 'session_recorded', 'human_reviewed', 'improvement_proposed', 'session_closed']),
  transitions: Object.freeze([
    Object.freeze({ from: 'not_recorded', to: 'session_recorded' }),
    Object.freeze({ from: 'session_recorded', to: 'human_reviewed' }),
    Object.freeze({ from: 'human_reviewed', to: 'improvement_proposed' }),
    Object.freeze({ from: 'improvement_proposed', to: 'session_closed' }),
  ]),
  storageMode: 'memory_session_only',
  isErpData: false,
  isBusinessData: false,
  persisted: false,
  changesPrice: false,
  changesBusinessState: false,
  triggersApproval: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalHumanAcceptanceFeedbackLoop(model = FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP'
    && model.states.length === 5 && model.transitions.length === 4
    && model.storageMode === 'memory_session_only' && model.isErpData === false
    && model.isBusinessData === false && model.persisted === false
    && model.changesPrice === false && model.changesBusinessState === false
    && model.triggersApproval === false && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
