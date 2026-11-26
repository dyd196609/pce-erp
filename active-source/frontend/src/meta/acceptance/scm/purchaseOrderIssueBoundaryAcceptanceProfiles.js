import { PURCHASE_ORDER_ISSUE_BOUNDARY } from '../../domain/scm/purchaseOrder/issue/purchaseOrderIssueBoundary.js'
import { SUPPLIER_RELEASE_CONTEXT } from '../../domain/scm/purchaseOrder/issue/supplierReleaseContext.js'
import { PURCHASE_ORDER_ISSUE_PREPARATION } from '../../domain/scm/purchaseOrder/issue/purchaseOrderIssuePreparation.js'
import { PURCHASE_ORDER_ISSUE_STATUS_CODE } from '../../domain/scm/purchaseOrder/issue/purchaseOrderIssueStatusDefinition.js'
import { PURCHASE_ORDER_ISSUE_RULE_SET_CODE } from '../../domain/scm/purchaseOrder/issue/purchaseOrderIssueRules.js'
import { PURCHASE_ORDER_ISSUE_ACTION_GUARD_CODE } from '../../domain/scm/purchaseOrder/issue/purchaseOrderIssueActionGuardRules.js'
import { PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY_CODE } from '../../domain/scm/purchaseOrder/issue/purchaseOrderIssueFinanceBoundary.js'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.10'

export const SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE',
  version: PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: PURCHASE_ORDER_ISSUE_BOUNDARY.objectCode,
  objects: Object.freeze([
    PURCHASE_ORDER_ISSUE_BOUNDARY.objectCode,
    SUPPLIER_RELEASE_CONTEXT.objectCode,
    PURCHASE_ORDER_ISSUE_PREPARATION.objectCode,
  ]),
  templates: Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  rules: Object.freeze([
    PURCHASE_ORDER_ISSUE_STATUS_CODE,
    PURCHASE_ORDER_ISSUE_RULE_SET_CODE,
    PURCHASE_ORDER_ISSUE_ACTION_GUARD_CODE,
    PURCHASE_ORDER_ISSUE_FINANCE_BOUNDARY_CODE,
  ]),
  collectors: Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR']),
  activationStatus: 'READY',
  activationMode: 'read_only',
  mode: 'read_only',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validatePurchaseOrderIssueBoundaryAcceptanceProfile(profile = SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.profileCode !== 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE') missing.push('profileCode')
  if (profile.objectCode !== 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY') missing.push('objectCode')
  if (profile.objects?.length !== 3) missing.push('objects')
  if (profile.rules?.length !== 4) missing.push('rules')
  if (!profile.templates?.length || !profile.collectors?.length) missing.push('acceptanceBindings')
  if (profile.activationStatus !== 'READY') missing.push('activationStatus')
  if (profile.activationMode !== 'read_only' || profile.mode !== 'read_only') missing.push('mode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
