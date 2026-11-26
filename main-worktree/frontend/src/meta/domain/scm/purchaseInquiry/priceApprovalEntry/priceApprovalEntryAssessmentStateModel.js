export const PRICE_APPROVAL_ENTRY_ASSESSMENT_STATE_VERSION = 'V1.14.2.8.6.3'

export const PRICE_APPROVAL_ENTRY_ASSESSMENT_STATES = Object.freeze([
  'not_assessed',
  'eligible',
  'not_eligible',
  'manual_review',
  'blocked',
])

export function isPriceApprovalEntryAssessmentState(status = '') {
  return PRICE_APPROVAL_ENTRY_ASSESSMENT_STATES.includes(status)
}
