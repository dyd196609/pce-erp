import { SUPPLIER_QUOTE_DOMAIN_MODEL } from '../../domain/scm/purchaseInquiry/quote/supplierQuoteDomainModel.js'
import { SUPPLIER_QUOTE_LINE_DOMAIN_MODEL } from '../../domain/scm/purchaseInquiry/quote/supplierQuoteLineDomainModel.js'
import { QUOTE_COMPARISON_DOMAIN_MODEL } from '../../domain/scm/purchaseInquiry/quote/quoteComparisonDomainModel.js'
import { SUPPLIER_QUOTE_VALIDATION_RULES } from '../../domain/scm/purchaseInquiry/quote/supplierQuoteValidationRules.js'
import { QUOTE_COMPARISON_RULES } from '../../domain/scm/purchaseInquiry/quote/quoteComparisonRules.js'
import { SUPPLIER_RECOMMENDATION_RULE_CODE } from '../../domain/scm/purchaseInquiry/quote/supplierRecommendationRules.js'
import { SUPPLIER_QUOTE_ACTION_GUARD_CODE } from '../../domain/scm/purchaseInquiry/quote/supplierQuoteActionGuardRules.js'
import { SUPPLIER_QUOTE_FINANCIAL_BOUNDARY_CODE } from '../../domain/scm/purchaseInquiry/quote/supplierQuoteFinancialBoundary.js'

export const SUPPLIER_QUOTE_COMPARISON_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.5.3'
const templates = Object.freeze(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2'])
const collectors = Object.freeze(['SCM_TRACE_COLLECTOR', 'SCM_ACTION_COLLECTOR'])

export const SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE',
  version: SUPPLIER_QUOTE_COMPARISON_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: SUPPLIER_QUOTE_DOMAIN_MODEL.objectCode,
  objects: Object.freeze([SUPPLIER_QUOTE_DOMAIN_MODEL.objectCode, SUPPLIER_QUOTE_LINE_DOMAIN_MODEL.objectCode]),
  templates,
  rules: Object.freeze([
    ...SUPPLIER_QUOTE_VALIDATION_RULES.map(rule => rule.ruleCode),
    SUPPLIER_QUOTE_ACTION_GUARD_CODE,
    SUPPLIER_QUOTE_FINANCIAL_BOUNDARY_CODE,
  ]),
  collectors,
  activationMode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export const SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE',
  version: SUPPLIER_QUOTE_COMPARISON_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: QUOTE_COMPARISON_DOMAIN_MODEL.objectCode,
  objects: Object.freeze([QUOTE_COMPARISON_DOMAIN_MODEL.objectCode]),
  templates,
  rules: Object.freeze([
    ...QUOTE_COMPARISON_RULES.map(rule => rule.ruleCode),
    SUPPLIER_RECOMMENDATION_RULE_CODE,
    SUPPLIER_QUOTE_ACTION_GUARD_CODE,
    SUPPLIER_QUOTE_FINANCIAL_BOUNDARY_CODE,
  ]),
  collectors,
  activationMode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

export function validateSupplierQuoteComparisonAcceptanceProfile(profile) {
  const missing = []
  if (!profile?.profileCode) missing.push('profileCode')
  if (!profile?.objects?.length) missing.push('objects')
  if (!profile?.templates?.length) missing.push('templates')
  if (!profile?.rules?.length) missing.push('rules')
  if (!profile?.collectors?.length) missing.push('collectors')
  if (profile?.activationMode !== 'read_only') missing.push('activationMode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
