import { PURCHASE_ORDER_DOMAIN_MODEL } from '../../domain/scm/purchaseOrder/domain/purchaseOrderDomainModel.js'
import { PURCHASE_ORDER_LINE_DOMAIN_MODEL } from '../../domain/scm/purchaseOrder/domain/purchaseOrderLineDomainModel.js'
import { PURCHASE_ORDER_SOURCE_REFERENCE_CODE } from '../../domain/scm/purchaseOrder/domain/purchaseOrderSourceReference.js'
import { PURCHASE_ORDER_STATUS_DEFINITION_CODE } from '../../domain/scm/purchaseOrder/domain/purchaseOrderStatusDefinition.js'
import { PURCHASE_ORDER_CREATION_CONTEXT_CODE } from '../../domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js'
import { PURCHASE_ORDER_DOMAIN_ACTION_GUARD_CODE } from '../../domain/scm/purchaseOrder/domain/purchaseOrderDomainActionGuardRules.js'
import { PURCHASE_ORDER_FINANCE_BOUNDARY_CODE } from '../../domain/scm/purchaseOrder/domain/purchaseOrderFinanceBoundary.js'

export const PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.6'

export const SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE',
  version: PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: PURCHASE_ORDER_DOMAIN_MODEL.objectCode,
  objects: Object.freeze([PURCHASE_ORDER_DOMAIN_MODEL.objectCode, PURCHASE_ORDER_LINE_DOMAIN_MODEL.objectCode]),
  templates: Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  rules: Object.freeze([
    PURCHASE_ORDER_SOURCE_REFERENCE_CODE,
    PURCHASE_ORDER_STATUS_DEFINITION_CODE,
    PURCHASE_ORDER_CREATION_CONTEXT_CODE,
    PURCHASE_ORDER_DOMAIN_ACTION_GUARD_CODE,
    PURCHASE_ORDER_FINANCE_BOUNDARY_CODE,
  ]),
  collectors: Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR']),
  activationMode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function validatePurchaseOrderDomainAcceptanceProfile(profile = SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.objectCode !== 'SCM_PURCHASE_ORDER') missing.push('objectCode')
  if (profile.objects?.length !== 2) missing.push('objects')
  if (!profile.templates?.length) missing.push('templates')
  if (profile.rules?.length !== 5) missing.push('rules')
  if (!profile.collectors?.length) missing.push('collectors')
  if (profile.activationMode !== 'read_only') missing.push('activationMode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
