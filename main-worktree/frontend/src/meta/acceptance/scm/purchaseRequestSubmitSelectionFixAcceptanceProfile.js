import { validatePurchaseRequestSubmitSelectionRuntime } from '../../runtime/purchaseRequestSubmitSelectionRuntime.js'

export const PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_REQUEST_SUBMIT_SELECTION_FIX',
  version: 'V1.14.2.8.7.8.1',
  status: 'SCM_PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_READY',
  route: '/scm/purchase-request',
  rowKey: 'requestNo',
  submitPermission: 'authenticated',
  submitSourceStatus: 'draft',
  submitTargetStatus: 'submitted',
  targetRequestNo: 'PR202608020008',
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  productionDataWritten: false,
  databaseSchemaChanged: false,
})

export function validatePurchaseRequestSubmitSelectionFixAcceptance(profile = PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE) {
  const runtime = validatePurchaseRequestSubmitSelectionRuntime()
  const valid = profile.profileCode === 'SCM_PURCHASE_REQUEST_SUBMIT_SELECTION_FIX'
    && profile.rowKey === 'requestNo' && profile.submitPermission === 'authenticated'
    && profile.submitSourceStatus === 'draft' && profile.submitTargetStatus === 'submitted'
    && profile.targetRequestNo === 'PR202608020008' && profile.gates.length === 8
    && profile.productionDataWritten === false && profile.databaseSchemaChanged === false
    && runtime.valid
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL' })
}
