import { PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL } from '../../domain/scm/purchaseOrder/gate/purchaseOrderCreationGateDomainModel.js'
import { PURCHASE_ORDER_CREATION_RULES } from '../../domain/scm/purchaseOrder/gate/purchaseOrderCreationRules.js'
import { PURCHASE_ORDER_CREATION_ELIGIBILITY_CODE } from '../../domain/scm/purchaseOrder/gate/purchaseOrderCreationEligibility.js'
import { PURCHASE_ORDER_CREATION_GATE_ACTION_GUARD_CODE } from '../../domain/scm/purchaseOrder/gate/purchaseOrderCreationGateActionGuardRules.js'
import { PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY_CODE } from '../../domain/scm/purchaseOrder/gate/purchaseOrderCreationFinanceBoundary.js'

export const PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.5'

export const SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE',
  version: PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.objectCode,
  objects: Object.freeze([PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.objectCode]),
  templates: Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  rules: Object.freeze([
    ...PURCHASE_ORDER_CREATION_RULES.map(rule => rule.ruleCode),
    PURCHASE_ORDER_CREATION_ELIGIBILITY_CODE,
    PURCHASE_ORDER_CREATION_GATE_ACTION_GUARD_CODE,
    PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY_CODE,
  ]),
  collectors: Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR']),
  activationMode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function validatePurchaseOrderCreationGateAcceptanceProfile(profile = SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.objectCode !== 'SCM_PURCHASE_ORDER_CREATION_GATE') missing.push('objectCode')
  if (profile.objects?.length !== 1) missing.push('objects')
  if (!profile.templates?.length) missing.push('templates')
  if (profile.rules?.length !== 7) missing.push('rules')
  if (!profile.collectors?.length) missing.push('collectors')
  if (profile.activationMode !== 'read_only') missing.push('activationMode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
