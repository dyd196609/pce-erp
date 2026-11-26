import { listPurchaseInquiryDomainObjects } from '../../domain/scm/purchaseInquiry/purchaseInquiryDomainModel.js'
import { PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS } from '../../domain/scm/purchaseInquiry/purchaseInquiryRelationshipModel.js'
import { PURCHASE_INQUIRY_STATUS_RULE_CODE } from '../../domain/scm/purchaseInquiry/purchaseInquiryStatusModel.js'
import { PURCHASE_INQUIRY_ACTION_RULE_CODE } from '../../domain/scm/purchaseInquiry/purchaseInquiryActionRules.js'
import { PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE_CODE } from '../../domain/scm/purchaseInquiry/purchaseInquiryFinancialBoundary.js'

export const PURCHASE_INQUIRY_ACCEPTANCE_PROFILE_VERSION = 'V1.14.2.8.4.21-R1'

export const PURCHASE_INQUIRY_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_ACCEPTANCE_PROFILE',
  version: PURCHASE_INQUIRY_ACCEPTANCE_PROFILE_VERSION,
  moduleCode: 'SCM',
  objectCode: 'SCM_PURCHASE_INQUIRY',
  objects: Object.freeze(listPurchaseInquiryDomainObjects().map(object => object.objectCode)),
  templates: Object.freeze(['PCE_ERP_UNIFIED_PAGE_ACCEPTANCE_STANDARD_V1.1', 'SCM-INQUIRY-001']),
  pageAcceptanceCode: 'SCM-PURCHASE-INQUIRY-ACT-001-R1',
  acceptanceSections: Object.freeze(['PAGE-COMMON', 'LIST', 'SCM-INQUIRY', 'GUIDE', 'CANARY', 'CHAIN']),
  customAcceptance: Object.freeze([
    '来源采购申请', '供应商候选', '询价对象编号', '询价状态', '询价明细',
    '供应商发送状态', '报价接收状态', '下一节点：核价',
  ]),
  guideContract: 'GUIDE-001..010',
  runtimeModes: Object.freeze(['production', 'canary_acceptance']),
  rules: Object.freeze([
    'SCM_STATUS_RULE',
    'SCM_TRACE_RULE',
    'SCM_ACTION_RULE',
    'SCM_FINANCIAL_BOUNDARY_RULE',
  ]),
  statusRule: PURCHASE_INQUIRY_STATUS_RULE_CODE,
  trace: Object.freeze(PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS.map(rule => rule.relationshipCode)),
  actions: PURCHASE_INQUIRY_ACTION_RULE_CODE,
  financialBoundary: PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE_CODE,
  runner: 'ENTERPRISE_PAGE_ACCEPTANCE_RUNNER',
  activationMode: 'explicit_approved_request_action',
  businessWriteCount: 1,
  productionUserDataWritten: false,
})

export function validatePurchaseInquiryAcceptanceProfile(profile = PURCHASE_INQUIRY_ACCEPTANCE_PROFILE) {
  const missing = []
  if (profile.objectCode !== 'SCM_PURCHASE_INQUIRY') missing.push('objectCode')
  if (profile.objects?.length !== 5) missing.push('objects')
  if (!profile.templates?.length) missing.push('templates')
  if (profile.rules?.length !== 4) missing.push('rules')
  if (profile.trace?.length !== 5) missing.push('trace')
  if (!profile.actions) missing.push('actions')
  if (!profile.financialBoundary) missing.push('financialBoundary')
  if (profile.activationMode !== 'explicit_approved_request_action') missing.push('activationMode')
  if (profile.acceptanceSections?.length !== 6) missing.push('acceptanceSections')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', valid: missing.length === 0, missing: Object.freeze(missing) })
}
