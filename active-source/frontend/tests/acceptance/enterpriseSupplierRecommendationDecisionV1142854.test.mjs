import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL, validateSupplierRecommendationDecisionDomainModel } from '../../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationDecisionDomainModel.js'
import { SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL, validateSupplierRecommendationEvidenceModel } from '../../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationEvidenceModel.js'
import { validateSupplierRecommendationDecision } from '../../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationValidationRules.js'
import { SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS, evaluateSupplierRecommendationActionGuard } from '../../src/meta/domain/scm/purchaseInquiry/recommendation/supplierRecommendationActionGuardRules.js'
import { PURCHASE_APPROVAL_BOUNDARY, evaluatePurchaseApprovalBoundary } from '../../src/meta/domain/scm/purchaseInquiry/recommendation/purchaseApprovalBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifySupplierRecommendationDecision, writeSupplierRecommendationDecisionVerification } from '../../scripts/verifySupplierRecommendationDecisionV1142854.mjs'

const decision = () => ({ inquiryId: 'INQ-DEFINITION', quoteComparisonId: 'COMPARISON-DEFINITION', recommendedSupplierId: 'SUPPLIER-DEFINITION', recommendationStatus: 'recommended', recommendationReason: 'best governed evidence', evidenceReferences: ['EVIDENCE-DEFINITION'], riskWarnings: [], approvalRequired: true })

test('SupplierRecommendationDecision包含八个必需字段', () => {
  assert.equal(validateSupplierRecommendationDecisionDomainModel().result, 'PASS')
  assert.deepEqual(SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.fields.map(field => field.name), ['inquiryId', 'quoteComparisonId', 'recommendedSupplierId', 'recommendationStatus', 'recommendationReason', 'evidenceReferences', 'riskWarnings', 'approvalRequired'])
})

test('推荐决策禁止自动创建和采购执行', () => {
  assert.equal(SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.createdAutomatically, false)
  assert.equal(SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.createsPurchaseOrder, false)
  assert.equal(SUPPLIER_RECOMMENDATION_DECISION_DOMAIN_MODEL.triggersApproval, false)
})

test('SupplierRecommendationEvidence保存四类证据字段', () => {
  assert.equal(validateSupplierRecommendationEvidenceModel().result, 'PASS')
  assert.deepEqual(SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL.fields.map(field => field.name), ['evidenceType', 'sourceObjectType', 'sourceObjectId', 'evidenceValue'])
})

test('完整推荐决策通过校验', () => {
  assert.equal(validateSupplierRecommendationDecision(decision()).result, 'PASS')
})

test('缺少证据引用时阻断', () => {
  assert.equal(validateSupplierRecommendationDecision({ ...decision(), evidenceReferences: [] }).result, 'FAIL')
})

test('只读证据和推荐查看Action允许', () => {
  for (const action of ['viewEvidence', 'compareQuote', 'viewRecommendation']) assert.equal(evaluateSupplierRecommendationActionGuard({ status: 'recommended', action }).result, 'PASS')
})

test('采购合同付款财务库存Action全部阻断', () => {
  for (const action of SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS) assert.equal(evaluateSupplierRecommendationActionGuard({ status: 'recommended', action }).result, 'FAIL')
})

test('采购审批前置边界只允许推荐证据引用', () => {
  assert.equal(evaluatePurchaseApprovalBoundary({ fact: 'recommendationEvidenceReference' }).result, 'PASS')
  for (const action of PURCHASE_APPROVAL_BOUNDARY.forbiddenExecutionActions) assert.equal(evaluatePurchaseApprovalBoundary({ action }).result, 'FAIL')
})

test('Finance voucher、payment、posting、ledger全部阻断', () => {
  for (const action of PURCHASE_APPROVAL_BOUNDARY.forbiddenFinanceActions) assert.equal(evaluatePurchaseApprovalBoundary({ action }).result, 'FAIL')
  assert.equal(PURCHASE_APPROVAL_BOUNDARY.financeExecutionAllowed, false)
})

test('Acceptance只读激活、自动验证和归档均无业务写入', async () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE')
  assert.equal(profile.activationMode, 'read_only')
  assert.equal(activation.businessWriteCount, 0)
  assert.equal(activation.productionUserDataWritten, false)
  const report = verifySupplierRecommendationDecision()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'supplier-recommendation-decision-'))
  await writeSupplierRecommendationDecisionVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'SUPPLIER_RECOMMENDATION_DECISION_MODEL_READY')
  assert.equal(archived.businessWriteCount, 0)
  assert.equal(archived.productionUserDataWritten, false)
})
