export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_MODEL_VERSION = 'V1.14.2.8.6.15'

export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STATES = Object.freeze([
  'not_started',
  'checking',
  'completed',
  'blocked',
  'manual_review',
])

export const FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL = Object.freeze({
  drillCode: 'SCM_FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL',
  version: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_MODEL_VERSION,
  drillKind: 'NON_EXECUTABLE_GOVERNANCE_CLOSURE_DRILL',
  fields: Object.freeze(['drillNo', 'inquiryNo', 'drillStatus', 'stageResults', 'blockedReasons', 'manualReviewReasons']),
  lifecycle: FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_STATES,
  executionMode: 'isolated_read_only',
  drillIsExecution: false,
  productionExecution: false,
  drillInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalEndToEndSafetyDrill(model = FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL) {
  const valid = model.drillCode === 'SCM_FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL'
    && model.drillKind === 'NON_EXECUTABLE_GOVERNANCE_CLOSURE_DRILL'
    && model.lifecycle.join(',') === 'not_started,checking,completed,blocked,manual_review'
    && model.executionMode === 'isolated_read_only'
    && model.drillIsExecution === false
    && model.productionExecution === false
    && model.drillInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
