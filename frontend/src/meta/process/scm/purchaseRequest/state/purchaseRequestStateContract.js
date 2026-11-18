export const PURCHASE_REQUEST_STATE_CONTRACT_VERSION = 'V1.14.2.8.18.2'
export const PURCHASE_REQUEST_STATE_CONTRACT_CODE = 'SCM_PURCHASE_REQUEST_STATE_CONTRACT'

export const PURCHASE_REQUEST_APPROVAL_STATUS = Object.freeze({
  DRAFT: 'draft', SUBMITTED: 'submitted', APPROVED: 'approved', REJECTED: 'rejected',
})

export const PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE = Object.freeze({
  CREATED: 'created', SUBMITTED: 'submitted', APPROVED: 'approved',
  AGREED_PRICE_CONFIRMATION_READY: 'agreed_price_confirmation_ready',
  INQUIRY_PREPARATION_READY: 'inquiry_preparation_ready',
  INQUIRY_PREPARATION_CREATED: 'inquiry_preparation_created', INQUIRY_STARTED: 'inquiry_started',
})

export const PURCHASE_REQUEST_CANONICAL_ACTION = Object.freeze({
  SUBMIT_APPROVAL: 'SUBMIT_APPROVAL', APPROVE: 'APPROVE',
  CREATE_INQUIRY_PREPARATION: 'CREATE_INQUIRY_PREPARATION', START_INQUIRY: 'START_PURCHASE_INQUIRY',
})

const approvalValues = Object.freeze(Object.values(PURCHASE_REQUEST_APPROVAL_STATUS))
const lifecycleValues = Object.freeze(Object.values(PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE))

function normalizeApproval(request = {}) {
  if (approvalValues.includes(request.approvalStatus)) return request.approvalStatus
  if (request.approvalStatus === 'completed') return PURCHASE_REQUEST_APPROVAL_STATUS.APPROVED
  if (request.approvalStatus === 'pending') return PURCHASE_REQUEST_APPROVAL_STATUS.SUBMITTED
  if (request.approvalStatus === 'not_submitted') return PURCHASE_REQUEST_APPROVAL_STATUS.DRAFT
  if (approvalValues.includes(request.statusCode)) return request.statusCode
  return PURCHASE_REQUEST_APPROVAL_STATUS.DRAFT
}

function normalizeLifecycle(request = {}, approvalStatus) {
  const supplied = request.businessLifecycleState || request.businessLifecycleStatus
  if (lifecycleValues.includes(supplied)) return supplied
  if (request.statusCode === 'inquiry_started') return PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE.INQUIRY_STARTED
  if (['inquiry_prepared', 'converted'].includes(request.statusCode)) {
    return PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE.INQUIRY_PREPARATION_CREATED
  }
  if (approvalStatus === PURCHASE_REQUEST_APPROVAL_STATUS.APPROVED) return PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE.APPROVED
  if (approvalStatus === PURCHASE_REQUEST_APPROVAL_STATUS.SUBMITTED) return PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE.SUBMITTED
  return PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATE.CREATED
}

export function readPurchaseRequestState(request = {}) {
  const approvalStatus = normalizeApproval(request)
  const businessLifecycleState = normalizeLifecycle(request, approvalStatus)
  return Object.freeze({ contractCode: PURCHASE_REQUEST_STATE_CONTRACT_CODE, approvalStatus, businessLifecycleState })
}

export function evaluatePurchaseRequestActionGuard(request = {}, actionCode = '') {
  const state = readPurchaseRequestState(request)
  const rules = {
    [PURCHASE_REQUEST_CANONICAL_ACTION.SUBMIT_APPROVAL]: state.approvalStatus === 'draft'
      && state.businessLifecycleState === 'created',
    [PURCHASE_REQUEST_CANONICAL_ACTION.APPROVE]: state.approvalStatus === 'submitted'
      && state.businessLifecycleState === 'submitted',
    [PURCHASE_REQUEST_CANONICAL_ACTION.CREATE_INQUIRY_PREPARATION]: state.approvalStatus === 'approved'
      && ['approved', 'inquiry_preparation_ready'].includes(state.businessLifecycleState),
    [PURCHASE_REQUEST_CANONICAL_ACTION.START_INQUIRY]: state.approvalStatus === 'approved'
      && state.businessLifecycleState === 'inquiry_preparation_created',
  }
  const allowed = rules[actionCode] === true
  return Object.freeze({ result: allowed ? 'PASS' : 'FAIL', allowed, actionCode, state,
    reason: allowed ? 'PURCHASE_REQUEST_STATE_CONTRACT_ALLOWED' : 'PURCHASE_REQUEST_STATE_CONTRACT_DENIED' })
}

export function transitionPurchaseRequestState(request = {}, actionCode = '') {
  const guard = evaluatePurchaseRequestActionGuard(request, actionCode)
  if (!guard.allowed) throw new Error(`${guard.reason}:${actionCode}`)
  const target = {
    SUBMIT_APPROVAL: { approvalStatus: 'submitted', businessLifecycleState: 'submitted', statusCode: 'submitted' },
    APPROVE: { approvalStatus: 'approved', businessLifecycleState: 'approved', statusCode: 'approved' },
    CREATE_INQUIRY_PREPARATION: { approvalStatus: 'approved', businessLifecycleState: 'inquiry_preparation_created', statusCode: 'approved' },
    START_PURCHASE_INQUIRY: { approvalStatus: 'approved', businessLifecycleState: 'inquiry_started', statusCode: 'approved' },
  }[actionCode]
  return Object.freeze({ ...request, ...target, businessLifecycleStatus: target.businessLifecycleState,
    stateContractCode: PURCHASE_REQUEST_STATE_CONTRACT_CODE })
}

export function validatePurchaseRequestStateContract() {
  const draft = { approvalStatus: 'draft', businessLifecycleState: 'created' }
  const submitted = transitionPurchaseRequestState(draft, 'SUBMIT_APPROVAL')
  const approved = transitionPurchaseRequestState(submitted, 'APPROVE')
  const preparation = transitionPurchaseRequestState(approved, 'CREATE_INQUIRY_PREPARATION')
  const valid = approvalValues.length === 4 && lifecycleValues.length === 6
    && submitted.approvalStatus === 'submitted' && approved.approvalStatus === 'approved'
    && preparation.businessLifecycleState === 'inquiry_preparation_created'
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
