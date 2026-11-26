import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SUPPLIER_QUOTE_DOMAIN_MODEL, validateSupplierQuoteDomainModel } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteDomainModel.js'
import { SUPPLIER_QUOTE_LINE_DOMAIN_MODEL, validateSupplierQuoteLineDomainModel } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteLineDomainModel.js'
import { QUOTE_COMPARISON_DOMAIN_MODEL, validateQuoteComparisonDomainModel } from '../src/meta/domain/scm/purchaseInquiry/quote/quoteComparisonDomainModel.js'
import { SUPPLIER_QUOTE_VALIDATION_RULES, validateSupplierQuote } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteValidationRules.js'
import { QUOTE_COMPARISON_RULES, evaluateQuoteComparison } from '../src/meta/domain/scm/purchaseInquiry/quote/quoteComparisonRules.js'
import { evaluateSupplierRecommendation } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierRecommendationRules.js'
import { SUPPLIER_QUOTE_ACTION_GUARD_RULES, SUPPLIER_QUOTE_FORBIDDEN_ACTIONS, evaluateSupplierQuoteActionGuard } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteActionGuardRules.js'
import { SUPPLIER_QUOTE_FINANCIAL_BOUNDARY, evaluateSupplierQuoteFinancialBoundary } from '../src/meta/domain/scm/purchaseInquiry/quote/supplierQuoteFinancialBoundary.js'
import { SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE, SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE, validateSupplierQuoteComparisonAcceptanceProfile } from '../src/meta/acceptance/scm/supplierQuoteComparisonAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.3'
export const TARGET_STATUS = 'SUPPLIER_QUOTE_COMPARISON_MODEL_READY'

const validQuote = Object.freeze({
  quoteNo: 'QUOTE-DEFINITION',
  inquiryNo: 'INQ-DEFINITION',
  supplierCode: 'SUPPLIER-DEFINITION',
  currency: 'CNY',
  validUntil: '2030-12-31T23:59:59.000Z',
  lines: Object.freeze([{ materialCode: 'MAT-DEFINITION', currency: 'CNY' }]),
  valid: true,
})
const validComparison = Object.freeze({ quoteList: Object.freeze([validQuote]), evaluationCriteria: Object.freeze(['price', 'delivery']), recommendedSupplier: 'SUPPLIER-DEFINITION', comparisonReason: 'best governed evidence' })
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifySupplierQuoteComparisonModel() {
  const activation = activateAcceptanceFramework('SCM')
  const profileCodes = activation.acceptanceProfiles?.map(profile => profile.profileCode) || []
  const quoteValidation = validateSupplierQuote(validQuote, { inquiryCurrency: 'CNY', asOfDate: '2026-08-02T00:00:00.000Z' })
  const comparison = evaluateQuoteComparison(validComparison)
  const recommendation = evaluateSupplierRecommendation({ validQuotes: [validQuote], comparisonCompleted: true, recommendedSupplier: 'SUPPLIER-DEFINITION', reason: 'best governed evidence', evidence: ['QUOTE-DEFINITION', 'COMPARISON-DEFINITION'] })
  const rules = Object.freeze([
    rule('QUOTE-001', 'SupplierQuote对象存在', SUPPLIER_QUOTE_DOMAIN_MODEL.objectCode === 'SCM_SUPPLIER_QUOTE' && validateSupplierQuoteDomainModel().result === 'PASS' && SUPPLIER_QUOTE_DOMAIN_MODEL.automaticCreation === false, SUPPLIER_QUOTE_DOMAIN_MODEL),
    rule('QUOTE-002', 'SupplierQuoteLine对象存在', SUPPLIER_QUOTE_LINE_DOMAIN_MODEL.objectCode === 'SCM_SUPPLIER_QUOTE_LINE' && validateSupplierQuoteLineDomainModel().result === 'PASS' && SUPPLIER_QUOTE_LINE_DOMAIN_MODEL.parentObject === 'SCM_SUPPLIER_QUOTE', SUPPLIER_QUOTE_LINE_DOMAIN_MODEL),
    rule('QUOTE-003', 'QuoteComparison对象存在', QUOTE_COMPARISON_DOMAIN_MODEL.objectCode === 'SCM_QUOTE_COMPARISON' && validateQuoteComparisonDomainModel().result === 'PASS' && QUOTE_COMPARISON_DOMAIN_MODEL.createsPurchaseOrder === false, QUOTE_COMPARISON_DOMAIN_MODEL),
    rule('QUOTE-004', '报价规则完整', SUPPLIER_QUOTE_VALIDATION_RULES.length === 5 && quoteValidation.result === 'PASS' && validateSupplierQuote({}, { inquiryCurrency: 'CNY', asOfDate: '2026-08-02T00:00:00.000Z' }).result === 'FAIL', quoteValidation),
    rule('QUOTE-005', '比价规则完整', QUOTE_COMPARISON_RULES.length === 3 && comparison.result === 'PASS' && evaluateQuoteComparison({ quoteList: [], evaluationCriteria: ['price'], recommendedSupplier: 'SUPPLIER-DEFINITION', comparisonReason: 'none' }).result === 'FAIL', comparison),
    rule('QUOTE-006', '推荐规则完整', recommendation.result === 'PASS' && recommendation.recommendedSupplier === 'SUPPLIER-DEFINITION' && recommendation.evidence.length === 2 && recommendation.createsPurchaseOrder === false, recommendation),
    rule('QUOTE-007', 'Action Guard完整', SUPPLIER_QUOTE_ACTION_GUARD_RULES.length > 0 && SUPPLIER_QUOTE_FORBIDDEN_ACTIONS.every(action => evaluateSupplierQuoteActionGuard({ status: 'valid', action }).result === 'FAIL') && evaluateSupplierQuoteActionGuard({ status: 'valid', action: 'compareQuote' }).result === 'PASS' && evaluateSupplierQuoteActionGuard({ status: 'compared', action: 'sendToPriceApproval' }).result === 'PASS', SUPPLIER_QUOTE_ACTION_GUARD_RULES),
    rule('QUOTE-008', 'Finance边界完整', SUPPLIER_QUOTE_FINANCIAL_BOUNDARY.allowedFacts.every(fact => evaluateSupplierQuoteFinancialBoundary({ fact }).result === 'PASS') && SUPPLIER_QUOTE_FINANCIAL_BOUNDARY.forbiddenActions.every(action => evaluateSupplierQuoteFinancialBoundary({ action }).result === 'FAIL'), SUPPLIER_QUOTE_FINANCIAL_BOUNDARY),
    rule('QUOTE-009', 'Acceptance Registry注册成功', activation.activated && ['SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE', 'SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE'].every(code => profileCodes.includes(code)) && validateSupplierQuoteComparisonAcceptanceProfile(SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE).valid && validateSupplierQuoteComparisonAcceptanceProfile(SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE).valid, profileCodes),
    rule('QUOTE-010', '无业务写入', [SUPPLIER_QUOTE_DOMAIN_MODEL, SUPPLIER_QUOTE_LINE_DOMAIN_MODEL, QUOTE_COMPARISON_DOMAIN_MODEL].every(model => model.persistenceMode === 'definition_only' && model.automaticCreation === false) && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionUserDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    models: Object.freeze({ supplierQuote: SUPPLIER_QUOTE_DOMAIN_MODEL.objectCode, supplierQuoteLine: SUPPLIER_QUOTE_LINE_DOMAIN_MODEL.objectCode, quoteComparison: QUOTE_COMPARISON_DOMAIN_MODEL.objectCode }),
    registry: Object.freeze({ activated: activation.activated, activationStatus: activation.activationStatus, profileCodes: Object.freeze(profileCodes) }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writeSupplierQuoteComparisonVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'supplier-quote-comparison'))
  const report = verifySupplierQuoteComparisonModel()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writeSupplierQuoteComparisonVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}
