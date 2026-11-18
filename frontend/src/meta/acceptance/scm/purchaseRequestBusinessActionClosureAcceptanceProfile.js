import { validatePurchaseRequestBusinessActionRuntime } from '../../runtime/purchaseRequestBusinessActionRuntime.js'

export const PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE',
  version: 'V1.14.2.8.7.8.2',
  status: 'SCM_PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_READY',
  route: '/scm/purchase-request',
  singleActions: Object.freeze(['submit', 'approve']),
  batchActions: Object.freeze(['batchSubmit', 'batchApprove']),
  statePath: Object.freeze(['draft', 'submitted', 'approved']),
  permissions: Object.freeze(['purchase_request.submit', 'purchase_request.approve']),
  approvalStatus: 'approved',
  automaticSubmit: false,
  automaticApprove: false,
  draftDirectApprove: false,
  databaseSchemaChanged: false,
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
})

export async function validatePurchaseRequestBusinessActionClosureAcceptance(profile = PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE) {
  const runtime = await validatePurchaseRequestBusinessActionRuntime()
  const valid = profile.profileCode === 'SCM_PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE'
    && profile.singleActions.length === 2 && profile.batchActions.length === 2
    && profile.statePath.join('>') === 'draft>submitted>approved'
    && profile.permissions.includes('purchase_request.submit') && profile.permissions.includes('purchase_request.approve')
    && profile.approvalStatus === 'approved' && profile.automaticSubmit === false
    && profile.automaticApprove === false && profile.draftDirectApprove === false
    && profile.databaseSchemaChanged === false && profile.gates.length === 8 && runtime.valid
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL' })
}
