export const PRICE_APPROVAL_CREATION_ASSESSMENT_STATE_VERSION = 'V1.14.2.8.6.4'

export const PRICE_APPROVAL_CREATION_ASSESSMENT_STATES = Object.freeze([
  'not_assessed',
  'ready',
  'manual_review',
  'blocked',
])

export function isPriceApprovalCreationAssessmentState(status = '') {
  return PRICE_APPROVAL_CREATION_ASSESSMENT_STATES.includes(status)
}
