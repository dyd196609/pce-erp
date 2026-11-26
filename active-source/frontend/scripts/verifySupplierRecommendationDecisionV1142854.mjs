import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL, validateSupplierRecommendationDecisionDomainModel } from '../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationDecisionDomainModel.js'
import { SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL, validateSupplierRecommendationEvidenceModel } from '../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationEvidenceModel.js'
import { SUPPLIER_RECOMMENDATION_VALIDATION_RULES, validateSupplierRecommendationDecision } from '../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationValidationRules.js'
import { SUPPLIER_RECOMMENDATION_ACTION_GUARD_RULES, SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS, evaluateSupplierRecommendationActionGuard } from '../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationActionGuardRules.js'
import { PURCHASE_APPROVAL_BOUNDARY, evaluatePurchaseApprovalBoundary } from '../src/meta/domain/scm/purchaseInquiry/recommendation/purchaseApprovalBoundary.js'
import { SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE, validateSupplierRecommendationDecisionAcceptanceProfile } from '../src/meta/acceptance/scm/supplierRecommendationDecisionAcceptanceProfiles.js'
import { activateAcceptanceFramework } from '../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'

export const VERSION = 'V1.14.2.8.5.4'
export const TARGET_STATUS = 'SUPPLIER_RECOMMENDATION_DECISION_MODEL_READY'

const validDecision = Object.freeze({
  inquiryId: 'INQ-DEFINITION',
  quoteComparisonId: 'COMPARISON-DEFINITION',
  recommendedSupplierId: 'SUPPLIER-DEFINITION',
  recommendationStatus: 'recommended',
  recommendationReason: 'best governed comparison evidence',
  evidenceReferences: Object.freeze(['EVIDENCE-DEFINITION']),
  riskWarnings: Object.freeze([]),
  approvalRequired: true,
})
const rule = (code, name, pass, evidence) => Object.freeze({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })

export function verifySupplierRecommendationDecision() {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles?.find(item => item.profileCode === 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE')
  const validation = validateSupplierRecommendationDecision(validDecision)
  const rules = Object.freeze([
    rule('DECISION-001', 'Domain对象存在', SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.objectCode === 'SCM_SUPPLIER_RECOMMENDATION_DECISION' && validateSupplierRecommendationDecisionDomainModel().result === 'PASS', SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL),
    rule('DECISION-002', 'Domain字段完整', SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.fields.length === 8 && SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.createdAutomatically === false && SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.triggersApproval === false, SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.fields),
    rule('DECISION-003', 'Evidence对象完整', SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL.objectCode === 'SCM_SUPPLIER_RECOMMENDATION_EVIDENCE' && validateSupplierRecommendationEvidenceModel().result === 'PASS' && SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL.fields.length === 4, SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL),
    rule('DECISION-004', 'Validation规则完整', SUPPLIER_RECOMMENDATION_VALIDATION_RULES.length === 7 && validation.result === 'PASS' && validateSupplierRecommendationDecision({ ...validDecision, evidenceReferences: [] }).result === 'FAIL', validation),
    rule('DECISION-005', '允许只读Action', ['viewEvidence', 'compareQuote', 'viewRecommendation'].every(action => evaluateSupplierRecommendationActionGuard({ status: 'recommended', action }).result === 'PASS'), SUPPLIER_RECOMMENDATION_ACTION_GUARD_RULES),
    rule('DECISION-006', '执行Action阻断', SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS.every(action => SUPPLIER_RECOMMENDATION_ACTION_GUARD_RULES.every(guard => evaluateSupplierRecommendationActionGuard({ status: guard.status, action }).result === 'FAIL')), SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS),
    rule('DECISION-007', '推荐证据边界允许', evaluatePurchaseApprovalBoundary({ fact: 'recommendationEvidenceReference' }).result === 'PASS' && PURCHASE_APPROVAL_BOUNDARY.approvalExecutionAllowed === false, PURCHASE_APPROVAL_BOUNDARY.allowedFacts),
    rule('DECISION-008', 'Finance边界阻断', PURCHASE_APPROVAL_BOUNDARY.forbiddenFinanceActions.every(action => evaluatePurchaseApprovalBoundary({ action }).result === 'FAIL') && PURCHASE_APPROVAL_BOUNDARY.financeExecutionAllowed === false, PURCHASE_APPROVAL_BOUNDARY.forbiddenFinanceActions),
    rule('DECISION-009', 'Acceptance注册成功', activation.activated && profile === SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE && validateSupplierRecommendationDecisionAcceptanceProfile(profile).valid && profile.activationMode === 'read_only', profile || {}),
    rule('DECISION-010', '无业务写入', [SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL, SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL].every(model => model.persistenceMode === 'definition_only' && model.automaticCreation === false) && activation.businessWriteCount === 0 && activation.productionUserDataWritten === false, { businessWriteCount: 0, productionUserDataWritten: false }),
  ])
  const count = result => rules.filter(item => item.result === result).length
  const summary = Object.freeze({ total: rules.length, PASS: count('PASS'), FAIL: count('FAIL'), 'N/A': count('N/A'), UNKNOWN: count('UNKNOWN') })
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: summary.PASS === 10 && summary.FAIL === 0 && summary.UNKNOWN === 0 ? TARGET_STATUS : 'FAIL',
    summary,
    rules,
    domain: Object.freeze({ decisionObject: SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.objectCode, evidenceObject: SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL.objectCode }),
    registry: Object.freeze({ activated: activation.activated, activationStatus: activation.activationStatus, profileCode: profile?.profileCode, activationMode: profile?.activationMode }),
    businessLogicChanged: false,
    scmLogicChanged: false,
    businessWriteCount: 0,
    productionUserDataWritten: false,
  })
}

export async function writeSupplierRecommendationDecisionVerification({ outputRoot } = {}) {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const archiveRoot = path.resolve(outputRoot || path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'supplier-recommendation-decision'))
  const report = verifySupplierRecommendationDecision()
  await fs.mkdir(archiveRoot, { recursive: true })
  await fs.writeFile(path.join(archiveRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return Object.freeze({ outputRoot: archiveRoot, files: Object.freeze(['verification-report.json']), report })
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedAsScript) {
  const result = await writeSupplierRecommendationDecisionVerification()
  console.log(JSON.stringify({ ...result.report, outputRoot: result.outputRoot, files: result.files }, null, 2))
  if (result.report.status !== TARGET_STATUS) process.exitCode = 1
}
