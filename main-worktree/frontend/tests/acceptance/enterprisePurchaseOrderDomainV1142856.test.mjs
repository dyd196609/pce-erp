import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { PURCHASE_ORDER_DOMAIN_MODEL, validatePurchaseOrderDomainModel } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainModel.js'
import { PURCHASE_ORDER_LINE_DOMAIN_MODEL, validatePurchaseOrderLineDomainModel } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderLineDomainModel.js'
import { PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS, PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS, evaluatePurchaseOrderSourceReference } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderSourceReference.js'
import { PURCHASE_ORDER_STATUS_DEFINITION } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderStatusDefinition.js'
import { buildPurchaseOrderCreationContext } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderCreationContext.js'
import { PURCHASE_ORDER_DOMAIN_ALLOWED_ACTIONS, PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS, evaluatePurchaseOrderDomainAction } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderDomainActionGuardRules.js'
import { PURCHASE_ORDER_FINANCE_BOUNDARY, evaluatePurchaseOrderFinanceBoundary } from '../../src/meta/domain/scm/purchaseOrder/domain/purchaseOrderFinanceBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyPurchaseOrderDomain, writePurchaseOrderDomainVerification } from '../../scripts/verifyPurchaseOrderDomainV1142856.mjs'

test('PurchaseOrderDomain包含七个必需字段', () => {
  assert.equal(validatePurchaseOrderDomainModel().result, 'PASS')
  assert.deepEqual(PURCHASE_ORDER_DOMAIN_MODEL.fields.map(field => field.name), ['sourceReferenceId', 'supplierId', 'orderStatus', 'orderLines', 'deliveryRequirement', 'paymentTermsReference', 'approvalReference'])
})

test('PurchaseOrder与Line均禁止自动创建交易', () => {
  assert.equal(validatePurchaseOrderLineDomainModel().result, 'PASS')
  for (const model of [PURCHASE_ORDER_DOMAIN_MODEL, PURCHASE_ORDER_LINE_DOMAIN_MODEL]) {
    assert.equal(model.createdAutomatically, false)
    assert.equal(model.createsBusinessTransaction, false)
  }
})

test('仅推荐决策和Creation Gate可作为来源', () => {
  for (const sourceObject of PURCHASE_ORDER_ALLOWED_SOURCE_OBJECTS) assert.equal(evaluatePurchaseOrderSourceReference({ sourceObject, sourceReferenceId: 'SOURCE-DEFINITION' }).result, 'PASS')
})

test('SupplierQuote和QuoteComparison禁止直接生成PO', () => {
  for (const sourceObject of PURCHASE_ORDER_FORBIDDEN_DIRECT_SOURCE_OBJECTS) assert.equal(evaluatePurchaseOrderSourceReference({ sourceObject, sourceReferenceId: 'SOURCE-DEFINITION' }).result, 'FAIL')
})

test('状态定义没有可执行迁移', () => {
  assert.equal(PURCHASE_ORDER_STATUS_DEFINITION.definitionOnly, true)
  assert.equal(PURCHASE_ORDER_STATUS_DEFINITION.transitionExecutionAllowed, false)
  assert.deepEqual(PURCHASE_ORDER_STATUS_DEFINITION.allowedTransitions, [])
})

test('创建上下文只组合证据不创建采购订单', () => {
  const context = buildPurchaseOrderCreationContext({ sourceObject: 'SCM_PURCHASE_ORDER_CREATION_GATE', sourceReferenceId: 'GATE-DEFINITION', supplierId: 'SUPPLIER-DEFINITION', gateEligibilityResult: 'ELIGIBLE', evidenceReferences: ['EVIDENCE-DEFINITION'] })
  assert.equal(context.contextStatus, 'READY')
  assert.equal(context.createsPurchaseOrder, false)
  assert.equal(context.createsBusinessTransaction, false)
})

test('仅允许查看定义、来源证据和创建上下文', () => {
  for (const action of PURCHASE_ORDER_DOMAIN_ALLOWED_ACTIONS) assert.equal(evaluatePurchaseOrderDomainAction({ status: 'definition', action }).result, 'PASS')
  assert.equal(evaluatePurchaseOrderDomainAction({ status: 'definition', action: 'unregisteredAction' }).result, 'FAIL')
})

test('采购订单执行动作全部阻断', () => {
  for (const action of PURCHASE_ORDER_DOMAIN_FORBIDDEN_ACTIONS) assert.equal(evaluatePurchaseOrderDomainAction({ status: 'context_ready', action }).result, 'FAIL')
})

test('Finance边界只允许金额引用', () => {
  for (const fact of PURCHASE_ORDER_FINANCE_BOUNDARY.allowedFacts) assert.equal(evaluatePurchaseOrderFinanceBoundary({ fact }).result, 'PASS')
  for (const action of PURCHASE_ORDER_FINANCE_BOUNDARY.forbiddenActions) assert.equal(evaluatePurchaseOrderFinanceBoundary({ action }).result, 'FAIL')
})

test('Acceptance只读激活且自动验证归档保持零写入', async () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationMode, 'read_only')
  const report = verifyPurchaseOrderDomain()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  assert.equal(report.businessWriteCount, 0)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-order-domain-'))
  await writePurchaseOrderDomainVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_ORDER_DOMAIN_MODEL_READY')
  assert.equal(archived.productionUserDataWritten, false)
})
