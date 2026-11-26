import { SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL } from '../../domain/scm/purchaseInquiry/recommendation/supplierRecommendationDecisionDomainModel.js'
import { SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL } from '../../domain/scm/purchaseInquiry/recommendation/supplierRecommendationEvidenceModel.js'
import { SUPPLIER_RECOMMENDATION_VALIDATION_RULES } from '../../domain/scm/purchaseInquiry/recommendation/supplierRecommendationValidationRules.js'
import { SUPPLIER_RECOMMENDATION_ACTION_GUARD_CODE } from '../../domain/scm/purchaseInquiry/recommendation/supplierRecommendationActionGuardRules.js'
import { PURCHASE_APPROVAL_BOUNDARY_CODE } from '../../domain/scm/purchaseInquiry/recommendation/purchaseApprovalBoundary.js'

export const SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.4'

export const SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE',
  version: SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.objectCode,
  objects: Object.freeze([
    SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.objectCode,
    SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL.objectCode,
  ]),
  templates: Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  rules: Object.freeze([
    ...SUPPLIER_RECOMMENDATION_VALIDATION_RULES.map(rule => rule.ruleCode),
    SUPPLIER_RECOMMENDATION_ACTION_GUARD_CODE,
    PURCHASE_APPROVAL_BOUNDARY_CODE,
  ]),
  collectors: Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR']),
  activationMode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function validateSupplierRecommendationDecisionAcceptanceProfile(profile = SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.objectCode !== 'SCM_SUPPLIER_RECOMMENDATION_DECISION') missing.push('objectCode')
  if (profile.objects?.length !== 2) missing.push('objects')
  if (!profile.templates?.length) missing.push('templates')
  if (!profile.rules?.length) missing.push('rules')
  if (!profile.collectors?.length) missing.push('collectors')
  if (profile.activationMode !== 'read_only') missing.push('activationMode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
