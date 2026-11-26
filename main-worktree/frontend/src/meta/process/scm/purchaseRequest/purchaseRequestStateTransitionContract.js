import { createProcessStateTransitionContract } from '../../contract/processStateTransitionContract.js'

export const PURCHASE_REQUEST_STATE_TRANSITION_CONTRACT = createProcessStateTransitionContract({
  modelCode: 'PURCHASE_REQUEST_RUNTIME_STATE',
  objectType: 'PurchaseRequest',
  initialState: 'new',
  states: ['new', 'draft', 'pending_approval', 'approved', 'inquiry_prepared'],
  transitions: [
    { actionCode: 'SAVE_PURCHASE_REQUEST', from: 'new', to: 'draft' },
    { actionCode: 'SUBMIT_PURCHASE_REQUEST', from: 'draft', to: 'pending_approval' },
    { actionCode: 'APPROVE_PURCHASE_REQUEST', from: 'pending_approval', to: 'approved' },
    { actionCode: 'GENERATE_INQUIRY_PREPARATION', from: 'approved', to: 'inquiry_prepared' },
  ],
})

export const PURCHASE_REQUEST_STATE_PROJECTIONS = Object.freeze({
  new: Object.freeze({ businessLifecycleStatus: 'created', approvalStatus: 'draft' }),
  draft: Object.freeze({ businessLifecycleStatus: 'created', approvalStatus: 'draft' }),
  pending_approval: Object.freeze({ businessLifecycleStatus: 'created', approvalStatus: 'submitted' }),
  approved: Object.freeze({ businessLifecycleStatus: 'approved', approvalStatus: 'approved' }),
  inquiry_prepared: Object.freeze({ businessLifecycleStatus: 'inquiry_preparation_created', approvalStatus: 'approved' }),
  inquiry_started: Object.freeze({ businessLifecycleStatus: 'inquiry_started', approvalStatus: 'approved' }),
})

export const PURCHASE_REQUEST_APPROVAL_STATES = Object.freeze(['draft', 'submitted', 'approved', 'rejected'])
export const PURCHASE_REQUEST_BUSINESS_LIFECYCLE_STATES = Object.freeze([
  'created', 'approved', 'inquiry_preparation_created', 'inquiry_started',
])

export function projectPurchaseRequestGovernedState(runtimeState = 'new') {
  return PURCHASE_REQUEST_STATE_PROJECTIONS[runtimeState] || PURCHASE_REQUEST_STATE_PROJECTIONS.new
}

export function validatePurchaseRequestStateSeparation() {
  const submitted = PURCHASE_REQUEST_STATE_PROJECTIONS.pending_approval
  const approved = PURCHASE_REQUEST_STATE_PROJECTIONS.approved
  const prepared = PURCHASE_REQUEST_STATE_PROJECTIONS.inquiry_prepared
  const valid = submitted.businessLifecycleStatus === 'created' && submitted.approvalStatus === 'submitted'
    && approved.businessLifecycleStatus === 'approved' && approved.approvalStatus === 'approved'
    && prepared.businessLifecycleStatus === 'inquiry_preparation_created'
    && prepared.approvalStatus === approved.approvalStatus
    && prepared !== approved
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL',
    valid,
    rule: 'APPROVAL_STATUS_AND_BUSINESS_STATUS_SEPARATED',
  })
}
