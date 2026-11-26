export const INQUIRY_PREPARATION_GUARD_VERSION = 'V1.14.2.8.7.9'

export const INQUIRY_PREPARATION_FORBIDDEN_ACTIONS = Object.freeze([
  'createFormalInquiry', 'createQuotationTask', 'sendSupplier', 'createQuotation',
  'startWorkflow', 'createPurchaseOrder', 'writeDatabase',
])

import { evaluatePurchaseRequestActionGuard } from '../../../process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

export function evaluateInquiryPreparationCreationGuard({ action = '', request = {} } = {}) {
  if (action === 'createInquiryPreparation') {
    const stateGuard = evaluatePurchaseRequestActionGuard(request, 'CREATE_INQUIRY_PREPARATION')
    return Object.freeze({ result: stateGuard.result, allowed: stateGuard.allowed,
      decision: stateGuard.allowed ? 'allow_preparation_only' : 'deny_state_contract',
      reason: stateGuard.reason, stateContractCode: stateGuard.state.contractCode,
      businessWriteType: 'session_preparation_object' })
  }
  const forbidden = INQUIRY_PREPARATION_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: forbidden ? 'PASS' : 'FAIL', allowed: false, decision: 'deny',
    reason: forbidden ? 'downstream_business_creation_frozen' : 'default_deny', databaseWritten: false })
}
