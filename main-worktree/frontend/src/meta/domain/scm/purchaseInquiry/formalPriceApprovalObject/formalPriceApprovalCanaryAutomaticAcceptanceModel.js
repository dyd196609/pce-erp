export const FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE_VERSION = 'V1.14.2.8.7.6.1'

export const FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE_VERSION,
  states: Object.freeze(['not_started', 'checking', 'completed', 'blocked']),
  currentState: 'not_started',
  triggerMode: 'manual_validation_trigger',
  executionMode: 'in_memory_assertion_only',
  producesBusinessResult: false,
  producesApprovalResult: false,
  updatesFeedbackLoop: false,
  startsWorkflow: false,
  persisted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCanaryAutomaticAcceptance(model = FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE'
    && model.states.join('|') === 'not_started|checking|completed|blocked'
    && model.currentState === 'not_started' && model.triggerMode === 'manual_validation_trigger'
    && model.executionMode === 'in_memory_assertion_only'
    && model.producesBusinessResult === false && model.producesApprovalResult === false
    && model.updatesFeedbackLoop === false && model.startsWorkflow === false
    && model.persisted === false && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
