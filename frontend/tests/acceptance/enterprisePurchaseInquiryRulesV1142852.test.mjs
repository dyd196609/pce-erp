import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { evaluatePurchaseInquiryTransitionGuard } from '../../src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryTransitionGuard.js'
import { evaluatePurchaseInquiryActionGuard } from '../../src/meta/domain/scm/purchaseInquiry/rules/purchaseInquiryActionGuardRules.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { getModuleAcceptanceProfile } from '../../src/meta/acceptance/registry/enterpriseAcceptanceFrameworkService.js'
import { verifyPurchaseInquiryRules, writePurchaseInquiryRulesVerification } from '../../scripts/verifyPurchaseInquiryRulesV1142852.mjs'

test('发布条件完整时允许 draft→issued', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'draft', toStatus: 'issued', facts: { inquiryNo: 'INQ-DEFINITION', lineCount: 1, sourcePurchaseRequest: 'PR-DEFINITION', supplierScope: ['SUPPLIER-DEFINITION'] } })
  assert.equal(result.result, 'PASS')
  assert.equal(result.businessRuleCode, 'INQ-RULE-001')
})

test('发布询价缺少明细时阻断', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'draft', toStatus: 'issued', facts: { inquiryNo: 'INQ-DEFINITION', lineCount: 0, sourcePurchaseRequest: 'PR-DEFINITION', supplierScope: ['SUPPLIER-DEFINITION'] } })
  assert.equal(result.result, 'FAIL')
  assert.ok(result.failedConditions.includes('lineCount_gt_0'))
})

test('发布询价缺少供应商范围时阻断', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'draft', toStatus: 'issued', facts: { inquiryNo: 'INQ-DEFINITION', lineCount: 1, sourcePurchaseRequest: 'PR-DEFINITION', supplierScope: [] } })
  assert.equal(result.result, 'FAIL')
  assert.ok(result.failedConditions.includes('supplierScope_exists'))
})

test('接收阶段无报价时阻断', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'issued', toStatus: 'quoted', facts: { quoteCount: 0, supplierExists: true, quoteLineCount: 1, currencyConsistent: true } })
  assert.equal(result.result, 'FAIL')
  assert.ok(result.failedConditions.includes('quoteCount_gt_0'))
})

test('进入评估缺少比较结果时阻断', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'quoted', toStatus: 'evaluating', facts: { validQuoteCount: 1 } })
  assert.equal(result.result, 'FAIL')
  assert.ok(result.failedConditions.includes('quoteComparison_exists'))
})

test('批准缺少推荐供应商时阻断', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'evaluating', toStatus: 'approved', facts: { comparisonReason: 'definition-only evidence' } })
  assert.equal(result.result, 'FAIL')
  assert.ok(result.failedConditions.includes('recommendedSupplier_exists'))
})

test('逆向迁移失败', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'approved', toStatus: 'evaluating' })
  assert.deepEqual({ result: result.result, reason: result.reason }, { result: 'FAIL', reason: 'reverse_transition_forbidden' })
})

test('跨级迁移失败', () => {
  const result = evaluatePurchaseInquiryTransitionGuard({ fromStatus: 'draft', toStatus: 'quoted' })
  assert.deepEqual({ result: result.result, reason: result.reason }, { result: 'FAIL', reason: 'skip_transition_forbidden' })
})

test('创建采购订单 Action 被阻断', () => {
  const result = evaluatePurchaseInquiryActionGuard({ status: 'approved', action: 'createPurchaseOrder' })
  assert.deepEqual({ result: result.result, decision: result.decision, reason: result.reason }, { result: 'FAIL', decision: 'deny', reason: 'dangerous_action_forbidden' })
})

test('规则 Profile 自动激活且验证归档不产生业务写入', async () => {
  const activation = activateAcceptanceFramework('SCM')
  const moduleProfile = getModuleAcceptanceProfile('SCM')
  const ruleProfile = activation.ruleProfiles.find(item => item.profileCode === 'SCM_PURCHASE_INQUIRY_RULE_PROFILE')
  assert.equal(activation.activated, true)
  assert.equal(ruleProfile.activationMode, 'read_only')
  assert.equal(moduleProfile.ruleProfiles.some(item => item.profileCode === ruleProfile.profileCode), true)
  assert.equal(activation.businessWriteCount, 0)
  assert.equal(activation.productionUserDataWritten, false)
  const report = verifyPurchaseInquiryRules()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-inquiry-rules-'))
  await writePurchaseInquiryRulesVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_INQUIRY_RULE_ENGINE_READY')
  assert.equal(archived.businessWriteCount, 0)
  assert.equal(archived.productionUserDataWritten, false)
})
