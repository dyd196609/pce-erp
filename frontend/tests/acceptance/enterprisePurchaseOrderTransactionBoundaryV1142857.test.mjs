import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { PURCHASE_ORDER_TRANSACTION_BOUNDARY, validatePurchaseOrderTransactionBoundary } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundary.js'
import { PURCHASE_ORDER_CREATION_REQUEST, validatePurchaseOrderCreationRequest } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderCreationRequest.js'
import { PURCHASE_ORDER_CREATION_REQUEST_STATUS } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderCreationRequestStatus.js'
import { PURCHASE_ORDER_APPROVAL_PREPARATION, buildPurchaseOrderApprovalPreparation } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderApprovalPreparation.js'
import { evaluatePurchaseOrderTransactionBoundary } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionBoundaryRules.js'
import { PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS, PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS, evaluatePurchaseOrderTransactionAction } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY, evaluatePurchaseOrderTransactionFinanceBoundary } from '../../src/meta/domain/scm/purchaseOrder/transaction/purchaseOrderTransactionFinanceBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyPurchaseOrderTransactionBoundary, writePurchaseOrderTransactionBoundaryVerification } from '../../scripts/verifyPurchaseOrderTransactionBoundaryV1142857.mjs'

const readyFacts = () => ({ supplierRecommendationDecisionExists: true, purchaseOrderCreationGateExists: true, gateEligibilityResult: 'ELIGIBLE', purchaseOrderDomainValid: true })

test('TransactionBoundary包含六个必需字段并禁止自动创建', () => {
  assert.equal(validatePurchaseOrderTransactionBoundary().result, 'PASS')
  assert.deepEqual(PURCHASE_ORDER_TRANSACTION_BOUNDARY.fields.map(field => field.name), ['purchaseOrderDomainId', 'creationGateId', 'boundaryStatus', 'transactionAllowed', 'blockingReasons', 'evidenceReferences'])
  assert.equal(PURCHASE_ORDER_TRANSACTION_BOUNDARY.createdAutomatically, false)
})

test('CreationRequest包含请求人理由风险和状态', () => {
  assert.equal(validatePurchaseOrderCreationRequest().result, 'PASS')
  for (const field of ['requester', 'requestReason', 'riskStatus', 'requestStatus']) assert.ok(PURCHASE_ORDER_CREATION_REQUEST.fields.some(item => item.name === field))
  assert.equal(PURCHASE_ORDER_CREATION_REQUEST.submitsWorkflow, false)
})

test('CreationRequest状态定义不执行迁移', () => {
  assert.equal(PURCHASE_ORDER_CREATION_REQUEST_STATUS.definitionOnly, true)
  assert.equal(PURCHASE_ORDER_CREATION_REQUEST_STATUS.transitionExecutionAllowed, false)
  assert.deepEqual(PURCHASE_ORDER_CREATION_REQUEST_STATUS.allowedTransitions, [])
})

test('四项边界条件完整时只返回未来事务准备判定', () => {
  const result = evaluatePurchaseOrderTransactionBoundary(readyFacts())
  assert.equal(result.transactionAllowed, true)
  assert.equal(result.boundaryResult, 'READY_FOR_FUTURE_TRANSACTION')
  assert.equal(result.executesTransaction, false)
  assert.equal(result.createsPurchaseOrder, false)
})

test('Gate非ELIGIBLE时事务边界阻断', () => {
  const result = evaluatePurchaseOrderTransactionBoundary({ ...readyFacts(), gateEligibilityResult: 'BLOCKED' })
  assert.equal(result.transactionAllowed, false)
  assert.ok(result.blockingReasons.includes('creation_gate_eligible'))
})

test('ApprovalPreparation只准备证据不提交审批', () => {
  const result = buildPurchaseOrderApprovalPreparation({ transactionAllowed: true, requestStatus: 'ready_for_approval', evidenceReferences: ['EVIDENCE-DEFINITION'] })
  assert.equal(result.preparationStatus, 'READY')
  assert.equal(result.submitsApproval, false)
  assert.equal(PURCHASE_ORDER_APPROVAL_PREPARATION.approvalExecutionAllowed, false)
})

test('Action Guard仅允许查看边界、请求和审批准备', () => {
  for (const action of PURCHASE_ORDER_TRANSACTION_ALLOWED_ACTIONS) assert.equal(evaluatePurchaseOrderTransactionAction({ status: 'evaluated', action }).result, 'PASS')
  assert.equal(evaluatePurchaseOrderTransactionAction({ status: 'evaluated', action: 'unregisteredAction' }).result, 'FAIL')
})

test('采购订单交易动作全部阻断', () => {
  for (const action of PURCHASE_ORDER_TRANSACTION_FORBIDDEN_ACTIONS) assert.equal(evaluatePurchaseOrderTransactionAction({ status: 'ready_for_future_transaction', action }).result, 'FAIL')
})

test('Finance边界只允许金额和成本引用', () => {
  for (const fact of PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY.allowedFacts) assert.equal(evaluatePurchaseOrderTransactionFinanceBoundary({ fact }).result, 'PASS')
  for (const action of PURCHASE_ORDER_TRANSACTION_FINANCE_BOUNDARY.forbiddenActions) assert.equal(evaluatePurchaseOrderTransactionFinanceBoundary({ action }).result, 'FAIL')
})

test('Acceptance只读激活且自动验证归档保持零写入', async () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationMode, 'read_only')
  const report = verifyPurchaseOrderTransactionBoundary()
  assert.deepEqual(report.summary, { total: 10, PASS: 10, FAIL: 0, 'N/A': 0, UNKNOWN: 0 })
  assert.equal(report.businessWriteCount, 0)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-order-transaction-boundary-'))
  await writePurchaseOrderTransactionBoundaryVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_ORDER_TRANSACTION_BOUNDARY_READY')
  assert.equal(archived.productionUserDataWritten, false)
})
