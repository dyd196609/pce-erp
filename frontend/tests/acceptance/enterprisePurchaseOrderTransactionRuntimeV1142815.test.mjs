import test from 'node:test'
import assert from 'node:assert/strict'

import { createQuoteComparisonContext, generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady, saveQuoteComparison } from '../../src/meta/runtime/quoteComparisonRuntime.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision,
  markSupplierRecommendationApprovalReady, saveSupplierRecommendationDecision } from '../../src/meta/runtime/supplierRecommendationRuntime.js'
import { createPurchaseOrderCreationGateContext, evaluatePurchaseOrderGateDecision,
  savePurchaseOrderGateDecision } from '../../src/meta/runtime/purchaseOrderCreationGateRuntime.js'
import { createPurchaseOrderTransactionContext, createPurchaseOrderTransaction,
  savePurchaseOrderTransaction } from '../../src/meta/runtime/purchaseOrderTransactionRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { createPurchaseOrderTransactionProcessAcceptanceDefinition,
  PURCHASE_ORDER_TRANSACTION_PROCESS006_STEPS, runPurchaseOrderTransactionEndToEndBusinessWalkthrough,
  validatePurchaseOrderTransactionProcessAcceptance } from '../../src/meta/process/scm/purchaseOrderTransaction/purchaseOrderTransactionProcessAcceptanceProfile.js'
import { validatePurchaseOrderGateTransactionHandoff } from '../../src/meta/process/scm/purchaseOrderTransaction/purchaseOrderGateTransactionHandoffContract.js'

let sequence = 0

function transactionChain(inquiryNo) {
  const quotes = ['A', 'B'].map((suffix, index) => ({
    quoteNo: `SQ-POT-${suffix}-${sequence}`, inquiryNo, supplierId: `SUP-POT-${suffix}`,
    supplierName: `Supplier ${suffix}`, currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
    lines: [{ materialCode: 'MAT-POT-001', materialName: 'Transaction Material', quantity: 10,
      unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }],
  }))
  const comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(
    generateQuoteComparisonFact(createQuoteComparisonContext(quotes))).object)
  const recommendation = markSupplierRecommendationApprovalReady(saveSupplierRecommendationDecision(
    generateSupplierRecommendationDecision(createSupplierRecommendationContext(comparison))).object)
  const gateContext = createPurchaseOrderCreationGateContext(recommendation)
  const gateDecision = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(gateContext)).object
  return { quotes, comparison, recommendation, gateDecision }
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      sequence += 1
      artifacts.request = { requestNo: `PR-POT-PROCESS-${sequence}` }
      return artifacts.request
    },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { inquiryNo: `PI-POT-PROCESS-${sequence}`, sourceRequestNo: request.requestNo }
      return artifacts.inquiry
    },
    async loadSupplierQuotes(inquiry) {
      artifacts.chain = transactionChain(inquiry.inquiryNo)
      artifacts.quotes = artifacts.chain.quotes
      return artifacts.quotes
    },
    async loadQuoteComparison() { artifacts.comparison = artifacts.chain.comparison; return artifacts.comparison },
    async loadSupplierRecommendation() { artifacts.recommendation = artifacts.chain.recommendation; return artifacts.recommendation },
    async loadPurchaseOrderGateDecision() { artifacts.gateDecision = artifacts.chain.gateDecision; return artifacts.gateDecision },
    async createTransactionContext(gateDecision) {
      artifacts.context = createPurchaseOrderTransactionContext(gateDecision)
      return artifacts.context
    },
    async createTransaction(context) {
      artifacts.transaction = createPurchaseOrderTransaction(context)
      return artifacts.transaction
    },
  }
}

test('PROCESS-006 executes the real path through purchase order transaction draft', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderTransactionEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_ORDER_TRANSACTION_PROCESS006_STEPS)
  assert.equal(walkthrough.finalState, 'draft')
})

test('PurchaseOrderTransaction profile passes every acceptance family', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderTransactionEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validatePurchaseOrderTransactionProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_PURCHASE_ORDER_TRANSACTION_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('gate handoff transfers supplier, details, quantity, amount and source chain', () => {
  sequence += 1
  const { gateDecision } = transactionChain(`PI-POT-HANDOFF-${sequence}`)
  const context = createPurchaseOrderTransactionContext(gateDecision)
  const validation = validatePurchaseOrderGateTransactionHandoff(gateDecision, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields,
    ['supplier', 'purchaseDetails', 'quantity', 'amountReference', 'sourceChain'])
})

test('this version operates only transaction_context_created to draft', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderTransactionEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createPurchaseOrderTransactionProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT').context
  context = executeProcessAction(definition, context, 'CREATE_PURCHASE_ORDER_TRANSACTION').context
  assert.equal(context.state, 'draft')
  const futureTransition = definition.stateModels[0].transitions.find(item => item.actionCode === 'SAVE_PURCHASE_ORDER_TRANSACTION')
  assert.equal(futureTransition.enabled, false)
})

test('save action is implemented as a locked boundary and cannot reach pending_issue', () => {
  sequence += 1
  const { gateDecision } = transactionChain(`PI-POT-SAVE-LOCK-${sequence}`)
  const transaction = createPurchaseOrderTransaction(createPurchaseOrderTransactionContext(gateDecision))
  const result = savePurchaseOrderTransaction(transaction)
  assert.equal(result.result, 'BLOCKED')
  assert.equal(result.reason, 'PURCHASE_ORDER_TRANSACTION_ADVANCE_LOCKED_V1142815')
  assert.equal(result.object.status, 'draft')
  assert.equal(result.stateTransitionExecuted, false)
})

test('draft creates no execution, publish, receive, inventory, invoice or payment facts', () => {
  sequence += 1
  const { gateDecision } = transactionChain(`PI-POT-BOUNDARY-${sequence}`)
  const transaction = createPurchaseOrderTransaction(createPurchaseOrderTransactionContext(gateDecision))
  assert.equal(transaction.purchaseOrderNo, null)
  assert.equal(transaction.purchaseOrderExecutionCreated, false)
  assert.equal(transaction.supplierPublished, false)
  assert.equal(transaction.goodsReceived, false)
  assert.equal(transaction.inventoryPosted, false)
  assert.equal(transaction.invoiceCreated, false)
  assert.equal(transaction.paymentCreated, false)
})
