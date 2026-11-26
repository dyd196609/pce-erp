import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL, validatePurchaseOrderCreationGateDomainModel } from '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGateDomainModel.js'
import { PURCHASE_ORDER_CREATION_RULES } from '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationRules.js'
import { evaluatePurchaseOrderCreationEligibility } from '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationEligibility.js'
import { PURCHASE_ORDER_CREATION_GATE_ALLOWED_ACTIONS, PURCHASE_ORDER_CREATION_GATE_FORBIDDEN_ACTIONS, evaluatePurchaseOrderCreationGateAction } from '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationGateActionGuardRules.js'
import { PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY, evaluatePurchaseOrderCreationFinanceBoundary } from '../../src/meta/domain/scm/purchaseOrder/gate/purchaseOrderCreationFinanceBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyPurchaseOrderCreationGate, writePurchaseOrderCreationGateVerification } from '../../scripts/verifyPurchaseOrderCreationGateV1142855.mjs'

const eligibleFacts = () => ({ recommendationDecisionExists: true, supplierQuoteValid: true, quoteComparisonCompleted: true, supplierValid: true })

test('PurchaseOrderCreationGate包含八个必需字段', () => {
  assert.equal(validatePurchaseOrderCreationGateDomainModel().result, 'PASS')
  assert.deepEqual(PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.fields.map(field => field.name), ['recommendationDecisionId', 'inquiryId', 'supplierId', 'gateStatus', 'eligibilityResult', 'blockingReasons', 'riskWarnings', 'evaluatedConditions'])
})

test('Gate禁止自动创建采购订单', () => {
  assert.equal(PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.createdAutomatically, false)
  assert.equal(PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.createsPurchaseOrder, false)
  assert.equal(PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL.executesBusinessAction, false)
})

test('四项创建条件全部满足时仅返回ELIGIBLE判定', () => {
  assert.equal(PURCHASE_ORDER_CREATION_RULES.length, 4)
  const result = evaluatePurchaseOrderCreationEligibility(eligibleFacts())
  assert.equal(result.eligibilityResult, 'ELIGIBLE')
  assert.equal(result.createsPurchaseOrder, false)
})

test('SupplierRecommendationDecision不存在时阻断', () => {
  const result = evaluatePurchaseOrderCreationEligibility({ ...eligibleFacts(), recommendationDecisionExists: false })
  assert.equal(result.eligibilityResult, 'BLOCKED')
  assert.ok(result.blockingReasons.includes('recommendation_decision_exists'))
})

test('报价比价或供应商无效时阻断并返回原因', () => {
  const result = evaluatePurchaseOrderCreationEligibility({ recommendationDecisionExists: true, supplierQuoteValid: false, quoteComparisonCompleted: false, supplierValid: false })
  assert.equal(result.eligibilityResult, 'BLOCKED')
  assert.deepEqual(result.blockingReasons, ['supplier_quote_valid', 'quote_comparison_completed', 'supplier_valid'])
})

test('Gate只允许查看结果、阻断原因和证据', () => {
  for (const action of PURCHASE_ORDER_CREATION_GATE_ALLOWED_ACTIONS) assert.equal(evaluatePurchaseOrderCreationGateAction({ status: 'evaluated', action }).result, 'PASS')
  assert.equal(evaluatePurchaseOrderCreationGateAction({ status: 'evaluated', action: 'unregisteredAction' }).result, 'FAIL')
})

test('采购订单及其他执行Action全部阻断', () => {
  for (const action of PURCHASE_ORDER_CREATION_GATE_FORBIDDEN_ACTIONS) assert.equal(evaluatePurchaseOrderCreationGateAction({ status: 'eligible', action }).result, 'FAIL')
})

test('Finance边界只允许估算采购成本引用', () => {
  assert.equal(evaluatePurchaseOrderCreationFinanceBoundary({ fact: 'estimatedPurchaseCostReference' }).result, 'PASS')
  for (const action of PURCHASE_ORDER_CREATION_FINANCE_BOUNDARY.forbiddenActions) assert.equal(evaluatePurchaseOrderCreationFinanceBoundary({ action }).result, 'FAIL')
})

test('Acceptance Profile自动只读激活', () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationMode, 'read_only')
})

test('自动验证与归档保持零业务写入', async () => {
  const report = verifyPurchaseOrderCreationGate()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  assert.equal(report.businessWriteCount, 0)
  assert.equal(report.productionUserDataWritten, false)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-order-creation-gate-'))
  await writePurchaseOrderCreationGateVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_ORDER_CREATION_GATE_MODEL_READY')
  assert.equal(archived.productionUserDataWritten, false)
})
