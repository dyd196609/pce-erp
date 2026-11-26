export const FORMAL_PRICE_APPROVAL_PROJECTION_STATE_VERSION = 'V1.14.2.8.6.5'

export const FORMAL_PRICE_APPROVAL_PROJECTION_STATES = Object.freeze([
  'not_created',
  'available',
  'incomplete',
  'blocked',
])

export function isFormalPriceApprovalProjectionState(status = '') {
  return FORMAL_PRICE_APPROVAL_PROJECTION_STATES.includes(status)
}
