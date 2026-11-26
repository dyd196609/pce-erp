import { PURCHASE_ORDER_TRANSACTION_BOUNDARY } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundary.js'
import { PURCHASE_ORDER_CREATION_REQUEST } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderCreationRequest.js'
import { PURCHASE_ORDER_CREATION_REQUEST_STATUS_CODE } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderCreationRequestStatus.js'
import { PURCHASE_ORDER_APPROVAL_PREPARATION, PURCHASE_ORDER_APPROVAL_PREPARATION_CODE } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderApprovalPreparation.js'
import { PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULE_SET_CODE } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundaryRules.js'
import { PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_CODE } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderTransactionActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY_CODE } from '../../domain/scm/purchaseOrder/transaction/purchaseOrderTransactionFinanceBoundary.js'

export const PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.7'

export const SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE',
  version: PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: PURCHASE_ORDER_TRANSACTION_BOUNDARY.objectCode,
  objects: Object.freeze([
    PURCHASE_ORDER_TRANSACTION_BOUNDARY.objectCode,
    PURCHASE_ORDER_CREATION_REQUEST.objectCode,
    PURCHASE_ORDER_APPROVAL_PREPARATION.objectCode,
  ]),
  templates: Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  rules: Object.freeze([
    PURCHASE_ORDER_TRANSACTION_BOUNDARY_RULE_SET_CODE,
    PURCHASE_ORDER_CREATION_REQUEST_STATUS_CODE,
    PURCHASE_ORDER_APPROVAL_PREPARATION_CODE,
    PURCHASE_ORDER_TRANSACTION_ACTION_GUARD_CODE,
    PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY_CODE,
  ]),
  collectors: Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR']),
  activationMode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function validatePurchaseOrderTransactionBoundaryAcceptanceProfile(profile = SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.objectCode !== 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY') missing.push('objectCode')
  if (profile.objects?.length !== 3) missing.push('objects')
  if (!profile.templates?.length) missing.push('templates')
  if (profile.rules?.length !== 5) missing.push('rules')
  if (!profile.collectors?.length) missing.push('collectors')
  if (profile.activationMode !== 'read_only') missing.push('activationMode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
