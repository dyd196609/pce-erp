import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  listPurchaseInquiryDomainObjects,
  resolvePurchaseInquiryDomainObject,
  validatePurchaseInquiryDomainObjectDefinition,
} from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryDomainModel.js'
import {
  PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS,
  PURCHASE_INQUIRY_TRACE_CHAIN,
  isPurchaseInquiryReverseGeneration,
} from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryRelationshipModel.js'
import {
  PURCHASE_INQUIRY_LIFECYCLE,
  PURCHASE_INQUIRY_STATUS_MODEL,
  evaluatePurchaseInquiryStatusTransition,
} from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryStatusModel.js'
import {
  PURCHASE_INQUIRY_ACTION_RULES,
  PURCHASE_INQUIRY_FORBIDDEN_DOWNSTREAM_ACTIONS,
  evaluatePurchaseInquiryAction,
} from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryActionRules.js'
import {
  PURCHASE_INQUIRY_FINANCIAL_BOUNDARY,
  evaluatePurchaseInquiryFinancialBoundary,
} from '../src/meta/domain/scm/purchaseInquiry/purchaseInquiryFinancialBoundary.js'
import {
  PURCHASE_INQUIRY_ACCEPTANCE_PROFILE,
  validatePurchaseInquiryAcceptanceProfile,
} from '../src/meta/acceptance/scm/purchaseInquiryAcceptanceProfile.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { getModuleAcceptanceProfile } from '../src/meta/acceptance/registry/enterpriseAcceptanceFrameworkService.js'

export const VERSION = 'V1.14.2.8.5.1'
export const TARGET_STATUS = 'PURCHASE_INQUIRY_DOMAIN_MODEL_READY'

const expectedLifecycle = ['draft', 'issued', 'quoted', 'evaluating', 'approved', 'closed']
const expectedChain = ['SCM_PURCHASE_REQUEST', 'SCM_PURCHASE_INQUIRY', 'SCM_SUPPLIER_QUOTE', 'SCM_QUOTE_COMPARISON', 'SCM_PRICE_APPROVAL', 'SCM_PURCHASE_ORDER']
const same = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifyPurchaseInquiryDomainModel() {
  const objects = listPurchaseInquiryDomainObjects()
  const inquiry = resolvePurchaseInquiryDomainObject('SCM_PURCHASE_INQUIRY')
  const inquiryLine = resolvePurchaseInquiryDomainObject('SCM_PURCHASE_INQUIRY_LINE')
  const quote = resolvePurchaseInquiryDomainObject('SCM_SUPPLIER_QUOTE')
  const quoteLine = resolvePurchaseInquiryDomainObject('SCM_SUPPLIER_QUOTE_LINE')
  const comparison = resolvePurchaseInquiryDomainObject('SCM_QUOTE_COMPARISON')
  const activation = activateAcceptanceFramework({ moduleCode: 'SCM' })
  const moduleProfile = getModuleAcceptanceProfile({ moduleCode: 'SCM' })
  const objectProfile = activation.objectProfiles?.find(profile => profile.objectCode === 'SCM_PURCHASE_INQUIRY')
  const reverseTransitions = PURCHASE_INQUIRY_LIFECYCLE.slice(1).map((status, index) => evaluatePurchaseInquiryStatusTransition({ fromStatus: status, toStatus: PURCHASE_INQUIRY_LIFECYCLE[index] }))
  const actionsComplete = PURCHASE_INQUIRY_ACTION_RULES.length === PURCHASE_INQUIRY_LIFECYCLE.length
    && PURCHASE_INQUIRY_ACTION_RULES.every(item => item.policy === 'explicit_whitelist_default_deny')
    && PURCHASE_INQUIRY_FORBIDDEN_DOWNSTREAM_ACTIONS.every(action => evaluatePurchaseInquiryAction({ status: 'draft', action }).result === 'FAIL')
  const financeComplete = ['quoteAmount', 'estimatedCost', 'priceReference'].every(fact => evaluatePurchaseInquiryFinancialBoundary({ fact }).result === 'PASS')
    && PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.forbiddenActions.every(action => evaluatePurchaseInquiryFinancialBoundary({ action }).result === 'FAIL')

  const rules = Object.freeze([
    rule('INQUIRY-001', 'PurchaseInquiry对象存在', inquiry?.businessObject === 'PurchaseInquiry' && validatePurchaseInquiryDomainObjectDefinition(inquiry).result === 'PASS', inquiry?.objectCode || ''),
    rule('INQUIRY-002', 'InquiryLine存在', inquiryLine?.businessObject === 'PurchaseInquiryLine' && inquiryLine.fields.some(field => field.name === 'materialCode'), inquiryLine?.objectCode || ''),
    rule('INQUIRY-003', 'SupplierQuote存在', quote?.businessObject === 'SupplierQuote' && quoteLine?.businessObject === 'SupplierQuoteLine' && quote.fields.some(field => field.name === 'supplierCode') && quoteLine.fields.some(field => field.name === 'quotePrice'), [quote?.objectCode, quoteLine?.objectCode]),
    rule('INQUIRY-004', 'QuoteComparison存在', comparison?.businessObject === 'QuoteComparison' && comparison.fields.some(field => field.name === 'recommendedSupplier'), comparison?.objectCode || ''),
    rule('INQUIRY-005', 'Trace关系正确', same(PURCHASE_INQUIRY_TRACE_CHAIN, expectedChain) && PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS.length === 5 && PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS.every(item => item.relationshipType === 'business_reference' && item.direction === 'forward' && item.reverseGenerationForbidden) && isPurchaseInquiryReverseGeneration('SCM_PURCHASE_INQUIRY', 'SCM_PURCHASE_REQUEST'), PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS.map(item => item.relationshipCode)),
    rule('INQUIRY-006', '状态机正确', same(PURCHASE_INQUIRY_LIFECYCLE, expectedLifecycle) && PURCHASE_INQUIRY_STATUS_MODEL.allowedTransitions.length === 5 && reverseTransitions.every(result => result.result === 'FAIL') && evaluatePurchaseInquiryStatusTransition({ fromStatus: 'draft', toStatus: 'quoted' }).result === 'FAIL', PURCHASE_INQUIRY_STATUS_MODEL),
    rule('INQUIRY-007', 'Action白名单正确', actionsComplete && evaluatePurchaseInquiryAction({ status: 'approved', action: 'sendToPriceApproval' }).result === 'PASS' && evaluatePurchaseInquiryAction({ status: 'approved', action: 'createPurchaseOrder' }).result === 'FAIL', { statuses: PURCHASE_INQUIRY_ACTION_RULES.map(item => item.status), policy: 'explicit_whitelist_default_deny' }),
    rule('INQUIRY-008', 'Finance边界正确', financeComplete && PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.createsPurchaseOrder === false && PURCHASE_INQUIRY_FINANCIAL_BOUNDARY.productionUserDataWritten === false, PURCHASE_INQUIRY_FINANCIAL_BOUNDARY),
    rule('INQUIRY-009', 'Acceptance Registry注册成功', validatePurchaseInquiryAcceptanceProfile().valid && activation.activated && objectProfile?.objects.length === 5 && moduleProfile.objectRegistrations?.some(profile => profile.objectCode === 'SCM_PURCHASE_INQUIRY'), objectProfile || PURCHASE_INQUIRY_ACCEPTANCE_PROFILE),
    rule('INQUIRY-010', '无业务写入', objects.every(object => object.persistenceMode === 'definition_only' && object.automaticCreation === false) && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { objectCount: objects.length, businessWriteCount: 0, productionUserDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    domain: Object.freeze({ objectCount: objects.length, relationshipCount: PURCHASE_INQUIRY_BUSINESS_RELATIONSHIPS.length, statusCount: PURCHASE_INQUIRY_LIFECYCLE.length, actionRuleCount: PURCHASE_INQUIRY_ACTION_RULES.length }),
    registryActivation: Object.freeze({ activated: activation.activated, activationStatus: activation.activationStatus, objectProfileCount: activation.objectProfileCount }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writePurchaseInquiryDomainVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-inquiry-domain'))
  const report = verifyPurchaseInquiryDomainModel()
  await fs.mkdir(archiveRoot, { recursive: true })
  await Promise.all([
    fs.writeFile(path.join(archiveRoot, 'domain-model.json'), `${JSON.stringify(listPurchaseInquiryDomainObjects(), null, 2)}\n`, 'utf8'),
    fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8'),
  ])
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['domain-model.json', 'verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writePurchaseInquiryDomainVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}

