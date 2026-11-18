import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import { PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL, buildPurchaseOrderTransactionDefinition, validatePurchaseOrderTransactionDomainModel } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionDomainModel.js'
import { PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL, validatePurchaseOrderTransactionLineDomainModel } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionLineDomainModel.js'
import { PURCHASE_ORDER_LIFECYCLE_STATES, PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleStateDefinition.js'
import { evaluatePurchaseOrderLifecycleRule } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderLifecycleRules.js'
import { PURCHASE_ORDER_TRANSACTION_MODEL_ALLOWED_ACTIONS, PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS, evaluatePurchaseOrderTransactionModelAction } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionActionGuardRules.js'
import { PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY, evaluatePurchaseOrderTransactionModelFinanceBoundary } from '../../src/meta/domain/scm/purchaseOrder/transactionModel/purchaseOrderTransactionFinanceBoundary.js'
import { activateAcceptanceFramework } from '../../src/meta/acceptance/registry/enterpriseAcceptanceActivator.js'
import { verifyPurchaseOrderTransactionModel, writePurchaseOrderTransactionModelVerification } from '../../scripts/verifyPurchaseOrderTransactionModelV1142859.mjs'

const completeTransaction = () => buildPurchaseOrderTransactionDefinition({
  transactionNo: 'PO-TXN', purchaseOrderDomainId: 'PO-DOMAIN', sourceReference: 'SOURCE', supplierId: 'SUPPLIER',
  orderLines: ['LINE'], totalAmountReference: 'TOTAL', currency: 'CNY', lifecycleStatus: 'draft', approvalReference: 'APPROVAL',
})

test('PurchaseOrderTransaction contains all required fields and cannot execute', () => {
  assert.equal(validatePurchaseOrderTransactionDomainModel().result, 'PASS')
  assert.deepEqual(PURCHASE_ORDER_TRANSACTION_DOMAIN_MODEL.fields.map(item => item.name), ['transactionNo', 'purchaseOrderDomainId', 'sourceReference', 'supplierId', 'orderLines', 'totalAmountReference', 'currency', 'lifecycleStatus', 'approvalReference'])
  const transaction = completeTransaction()
  assert.equal(transaction.definitionStatus, 'ready')
  assert.equal(transaction.createdAutomatically, false)
  assert.equal(transaction.createsBusinessTransaction, false)
  assert.equal(transaction.executesTransaction, false)
})

test('PurchaseOrderTransaction blocks incomplete definitions', () => {
  const result = buildPurchaseOrderTransactionDefinition({})
  assert.equal(result.definitionStatus, 'blocked')
  assert.equal(result.missingFields.length, 9)
  assert.equal(result.businessWriteCount, 0)
})

test('PurchaseOrderTransactionLine is an isolated definition-only child', () => {
  assert.equal(validatePurchaseOrderTransactionLineDomainModel().result, 'PASS')
  assert.equal(PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL.independentCreationAllowed, false)
  assert.equal(PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL.createsBusinessTransaction, false)
  assert.equal(PURCHASE_ORDER_TRANSACTION_LINE_DOMAIN_MODEL.executesTransaction, false)
})

test('Lifecycle defines seven statuses without automatic transitions', () => {
  assert.deepEqual(PURCHASE_ORDER_LIFECYCLE_STATES, ['draft', 'pending_approval', 'approved', 'issued', 'partially_received', 'completed', 'cancelled'])
  assert.equal(PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION.automaticTransitionAllowed, false)
  assert.equal(PURCHASE_ORDER_LIFECYCLE_STATE_DEFINITION.transitionExecutionAllowed, false)
  const relationship = evaluatePurchaseOrderLifecycleRule({ from: 'draft', to: 'pending_approval' })
  assert.equal(relationship.result, 'PASS')
  assert.equal(relationship.transitionExecuted, false)
})

test('Action Guard allows views and denies transaction execution', () => {
  for (const action of PURCHASE_ORDER_TRANSACTION_MODEL_ALLOWED_ACTIONS) assert.equal(evaluatePurchaseOrderTransactionModelAction({ status: 'ready', action }).result, 'PASS')
  for (const action of PURCHASE_ORDER_TRANSACTION_MODEL_FORBIDDEN_ACTIONS) assert.equal(evaluatePurchaseOrderTransactionModelAction({ status: 'ready', action }).result, 'FAIL')
  assert.equal(evaluatePurchaseOrderTransactionModelAction({ status: 'ready', action: 'unregisteredAction' }).result, 'FAIL')
})

test('Finance Boundary allows references and denies finance execution', () => {
  for (const fact of PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY.allowedFacts) assert.equal(evaluatePurchaseOrderTransactionModelFinanceBoundary({ fact }).result, 'PASS')
  for (const action of PURCHASE_ORDER_TRANSACTION_MODEL_FINANCE_BOUNDARY.forbiddenActions) assert.equal(evaluatePurchaseOrderTransactionModelFinanceBoundary({ action }).result, 'FAIL')
})

test('Acceptance profile activates READY in read_only mode', () => {
  const activation = activateAcceptanceFramework('SCM')
  const profile = activation.acceptanceProfiles.find(item => item.profileCode === 'SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE')
  assert.equal(activation.activationStatus, 'READY')
  assert.equal(profile.activationStatus, 'READY')
  assert.equal(profile.mode, 'read_only')
})

test('Verifier reports all categories PASS with unchanged database SHA', async () => {
  const report = verifyPurchaseOrderTransactionModel()
  assert.deepEqual(report.categoryResults, { Transaction: 'PASS', Line: 'PASS', Lifecycle: 'PASS', Guard: 'PASS', Finance: 'PASS', Acceptance: 'PASS' })
  assert.equal(report.status, 'PURCHASE_ORDER_TRANSACTION_MODEL_READY')
  assert.equal(report.businessWriteCount, 0)
  assert.equal(report.databaseProtection.databaseShaUnchanged, true)
  assert.equal(report.productionDataWritten, false)
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), 'purchase-order-transaction-model-'))
  await writePurchaseOrderTransactionModelVerification({ outputRoot })
  const archived = JSON.parse(await readFile(path.join(outputRoot, 'verification-report.json'), 'utf8'))
  assert.equal(archived.status, 'PURCHASE_ORDER_TRANSACTION_MODEL_READY')
})
