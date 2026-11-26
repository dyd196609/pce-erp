import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readdir, readFile } from 'node:fs/promises'
import template from '../../src/meta/acceptance/templates/scmBusinessPageAcceptanceTemplateV2.json' with { type: 'json' }
import { listScmAcceptanceObjects, resolveScmAcceptanceObject } from '../../src/meta/acceptance/scm/scmAcceptanceObjectModel.js'
import { SCM_TRACE_ACCEPTANCE_RULES, evaluateScmTraceRelationship, isReverseScmGeneration } from '../../src/meta/acceptance/scm/scmTraceAcceptanceRules.js'
import { SCM_STATUS_ACCEPTANCE_RULES, evaluateScmStatusTransition } from '../../src/meta/acceptance/scm/scmStatusAcceptanceRules.js'
import { SCM_ACTION_ACCEPTANCE_RULES, evaluateScmAction } from '../../src/meta/acceptance/scm/scmActionAcceptanceRules.js'
import { SCM_FINANCIAL_BOUNDARY, evaluateScmFinancialBoundary } from '../../src/meta/acceptance/scm/scmFinancialBoundaryRules.js'
import { verifyScmAcceptanceModel, writeScmAcceptanceModelArchive } from '../../scripts/verifyScmAcceptanceModelV1142823.mjs'

test('对象注册覆盖 PurchaseRequest、PurchaseInquiry 与 PurchaseOrder', () => {
  assert.deepEqual(listScmAcceptanceObjects().map(item => item.businessObject), ['PurchaseRequest', 'PurchaseInquiry', 'PurchaseOrder'])
  assert.equal(resolveScmAcceptanceObject('PurchaseRequest').objectCode, 'SCM_PURCHASE_REQUEST')
})

test('Trace 关系覆盖完整采购链且必需事实一致时 PASS', () => {
  assert.equal(SCM_TRACE_ACCEPTANCE_RULES.length, 6)
  const rule = SCM_TRACE_ACCEPTANCE_RULES[0]
  assert.equal(evaluateScmTraceRelationship({ ...rule, traceId: 'TRACE-001', sourceTraceId: 'TRACE-001', targetTraceId: 'TRACE-001' }).result, 'PASS')
})

test('状态机只接受相邻正向迁移', () => {
  assert.equal(SCM_STATUS_ACCEPTANCE_RULES.length, 3)
  assert.equal(evaluateScmStatusTransition({ objectCode: 'SCM_PURCHASE_REQUEST', fromStatus: 'draft', toStatus: 'submitted' }).result, 'PASS')
  assert.equal(evaluateScmStatusTransition({ objectCode: 'SCM_PURCHASE_REQUEST', fromStatus: 'draft', toStatus: 'approved' }).result, 'FAIL')
})

test('状态逆转与 Trace 反向生成均被禁止', () => {
  assert.equal(evaluateScmStatusTransition({ objectCode: 'SCM_PURCHASE_ORDER', fromStatus: 'closed', toStatus: 'draft' }).result, 'FAIL')
  assert.equal(isReverseScmGeneration('SCM_PURCHASE_ORDER', 'SCM_PURCHASE_REQUEST'), true)
})

test('Action 使用逐状态白名单并默认拒绝', () => {
  assert.equal(SCM_ACTION_ACCEPTANCE_RULES.length, 15)
  assert.equal(evaluateScmAction({ objectCode: 'SCM_PURCHASE_REQUEST', status: 'draft', action: 'submit' }).result, 'PASS')
  assert.equal(evaluateScmAction({ objectCode: 'SCM_PURCHASE_REQUEST', status: 'approved', action: 'modify' }).result, 'FAIL')
  assert.equal(evaluateScmAction({ objectCode: 'SCM_PURCHASE_REQUEST', status: 'draft', action: 'unregisteredAction' }).result, 'FAIL')
})

test('Finance 边界允许金额事实但拒绝付款、银行与记账动作', () => {
  assert.equal(evaluateScmFinancialBoundary({ fact: 'purchaseAmount', financeImpact: false }).result, 'PASS')
  for (const action of SCM_FINANCIAL_BOUNDARY.forbiddenActions) assert.equal(evaluateScmFinancialBoundary({ action }).result, 'FAIL')
  assert.equal(SCM_FINANCIAL_BOUNDARY.productionUserDataWritten, false)
})

test('Canary 隔离保持只读且不调用生产 API', () => {
  assert.deepEqual(template.canaryIsolation, { dataMode: 'canary_acceptance', readOnly: true, productionApiCallCount: 0, businessWriteCount: 0, productionUserDataWritten: false })
})

test('缺失事实和未知对象统一治理为 UNKNOWN', () => {
  assert.equal(evaluateScmTraceRelationship({}).result, 'UNKNOWN')
  assert.equal(evaluateScmStatusTransition({ objectCode: 'SCM_UNKNOWN', fromStatus: 'draft', toStatus: 'closed' }).result, 'UNKNOWN')
  assert.equal(evaluateScmAction({ objectCode: 'SCM_PURCHASE_ORDER', status: 'not-modelled', action: 'issue' }).result, 'UNKNOWN')
  assert.equal(evaluateScmFinancialBoundary({}).result, 'UNKNOWN')
})

test('SCM V2 模板精确继承母模板并包含 SCM-001 至 SCM-008', () => {
  assert.equal(template.extends, 'PCE-ENTERPRISE-PAGE-ACCEPTANCE-MASTER-V1')
  assert.equal(template.extendsFile, 'enterprise_page_master_template.json')
  assert.deepEqual(template.checks.map(item => item.id), ['SCM-001','SCM-002','SCM-003','SCM-004','SCM-005','SCM-006','SCM-007','SCM-008'])
})

test('自动验证恰好 10 PASS、0 FAIL、0 UNKNOWN', () => {
  const report = verifyScmAcceptanceModel()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  assert.equal(report.status, 'SCM_ACCEPTANCE_MODEL_READY')
  assert.equal(report.productionUserDataWritten, false)
})

test('归档输出包含七个指定文件且保护报告可复读', async () => {
  const archiveRoot = await mkdtemp(path.join(os.tmpdir(), 'scm-acceptance-model-'))
  const result = await writeScmAcceptanceModelArchive({ archiveRoot })
  assert.deepEqual((await readdir(archiveRoot)).sort(), result.files.toSorted())
  const report = JSON.parse(await readFile(path.join(archiveRoot, 'verification-report.json'), 'utf8'))
  assert.equal(report.status, 'SCM_ACCEPTANCE_MODEL_READY')
  assert.equal(report.businessWriteCount, 0)
  assert.equal(report.productionUserDataWritten, false)
})

