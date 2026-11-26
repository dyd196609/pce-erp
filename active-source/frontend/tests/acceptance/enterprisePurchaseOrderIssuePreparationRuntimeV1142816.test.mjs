import test from 'node:test'
import assert from 'node:assert/strict'

import { createQuoteComparisonContext, generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady, saveQuoteComparison } from '../../src/meta/runtime/quoteComparisonRuntime.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision,
  markSupplierRecommendationApprovalReady, saveSupplierRecommendationDecision } from '../../src/meta/runtime/supplierRecommendationRuntime.js'
import { createPurchaseOrderCreationGateContext, evaluatePurchaseOrderGateDecision,
  savePurchaseOrderGateDecision } from '../../src/meta/runtime/purchaseOrderCreationGateRuntime.js'
import { createPurchaseOrderTransactionContext, createPurchaseOrderTransaction } from '../../src/meta/runtime/purchaseOrderTransactionRuntime.js'
import { createPurchaseOrderIssuePreparationContext, checkPurchaseOrderIssuePreparation,
  savePurchaseOrderIssuePreparation } from '../../src/meta/runtime/purchaseOrderIssuePreparationRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { createPurchaseOrderIssuePreparationProcessAcceptanceDefinition,
  PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS006_STEPS, runPurchaseOrderIssuePreparationEndToEndBusinessWalkthrough,
  validatePurchaseOrderIssuePreparationProcessAcceptance } from '../../src/meta/process/scm/purchaseOrderIssuePreparation/purchaseOrderIssuePreparationProcessAcceptanceProfile.js'
import { validatePurchaseOrderTransactionIssuePreparationHandoff } from '../../src/meta/process/scm/purchaseOrderIssuePreparation/purchaseOrderTransactionIssuePreparationHandoffContract.js'

let sequence = 0

function issuePreparationChain(inquiryNo) {
  const quotes = ['A', 'B'].map((suffix, index) => ({
    quoteNo: `SQ-POIP-${suffix}-${sequence}`, inquiryNo, supplierId: `SUP-POIP-${suffix}`,
    supplierName: `Supplier ${suffix}`, currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
    lines: [{ materialCode: 'MAT-POIP-001', materialName: 'Issue Preparation Material', quantity: 10,
      unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }],
  }))
  const comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(
    generateQuoteComparisonFact(createQuoteComparisonContext(quotes))).object)
  const recommendation = markSupplierRecommendationApprovalReady(saveSupplierRecommendationDecision(
    generateSupplierRecommendationDecision(createSupplierRecommendationContext(comparison))).object)
  const gateDecision = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(
    createPurchaseOrderCreationGateContext(recommendation))).object
  const transaction = createPurchaseOrderTransaction(createPurchaseOrderTransactionContext(gateDecision))
  return { quotes, comparison, recommendation, gateDecision, transaction }
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      sequence += 1
      artifacts.request = { requestNo: `PR-POIP-PROCESS-${sequence}` }
      return artifacts.request
    },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { inquiryNo: `PI-POIP-PROCESS-${sequence}`, sourceRequestNo: request.requestNo }
      return artifacts.inquiry
    },
    async loadSupplierQuotes(inquiry) {
      artifacts.chain = issuePreparationChain(inquiry.inquiryNo)
      artifacts.quotes = artifacts.chain.quotes
      return artifacts.quotes
    },
    async loadQuoteComparison() { artifacts.comparison = artifacts.chain.comparison; return artifacts.comparison },
    async loadSupplierRecommendation() { artifacts.recommendation = artifacts.chain.recommendation; return artifacts.recommendation },
    async loadPurchaseOrderGateDecision() { artifacts.gateDecision = artifacts.chain.gateDecision; return artifacts.gateDecision },
    async loadPurchaseOrderTransaction() { artifacts.transaction = artifacts.chain.transaction; return artifacts.transaction },
    async createIssuePreparationContext(transaction) {
      artifacts.context = createPurchaseOrderIssuePreparationContext(transaction)
      return artifacts.context
    },
    async checkIssueRequirements(context) {
      artifacts.preparation = checkPurchaseOrderIssuePreparation(context)
      return artifacts.preparation
    },
    async saveIssuePreparation(preparation) {
      const result = savePurchaseOrderIssuePreparation(preparation)
      artifacts.preparation = result.object
      return result
    },
  }
}

test('PROCESS-006 executes purchase request through purchase order issue preparation', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssuePreparationEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS006_STEPS)
  assert.equal(artifacts.preparation.status, 'ready_for_issue')
})

test('IssuePreparation profile passes all acceptance families', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssuePreparationEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validatePurchaseOrderIssuePreparationProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_PURCHASE_ORDER_ISSUE_PREPARATION_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('transaction handoff transfers supplier, lines, quantity, amount, delivery and source chain', () => {
  sequence += 1
  const { transaction } = issuePreparationChain(`PI-POIP-HANDOFF-${sequence}`)
  const context = createPurchaseOrderIssuePreparationContext(transaction)
  const validation = validatePurchaseOrderTransactionIssuePreparationHandoff(transaction, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields,
    ['supplier', 'orderDetails', 'quantity', 'amountReference', 'deliveryRequirements', 'sourceChain'])
})

test('three Action Contracts close the ready_for_issue state path', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssuePreparationEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createPurchaseOrderIssuePreparationProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_ISSUE_PREPARATION_CONTEXT').context
  context = executeProcessAction(definition, context, 'CHECK_ISSUE_REQUIREMENTS').context
  context = executeProcessAction(definition, context, 'SAVE_ISSUE_PREPARATION').context
  assert.equal(context.state, 'ready_for_issue')
})

test('missing delivery requirement creates a blocked preparation', () => {
  sequence += 1
  const { transaction } = issuePreparationChain(`PI-POIP-BLOCK-${sequence}`)
  const invalidTransaction = { ...transaction, transactionNo: `${transaction.transactionNo}-BLOCK`,
    purchaseDetails: transaction.purchaseDetails.map(item => ({ ...item, deliveryDate: '' })) }
  const context = createPurchaseOrderIssuePreparationContext(invalidTransaction)
  const saved = savePurchaseOrderIssuePreparation(checkPurchaseOrderIssuePreparation(context)).object
  assert.equal(saved.status, 'blocked')
  assert.ok(saved.blockedReasons.includes('POIP-DELIVERY-REQUIREMENTS'))
})

test('ready_for_issue never issues, sends, receives, posts inventory, invoices or pays', () => {
  sequence += 1
  const { transaction } = issuePreparationChain(`PI-POIP-BOUNDARY-${sequence}`)
  const context = createPurchaseOrderIssuePreparationContext(transaction)
  const saved = savePurchaseOrderIssuePreparation(checkPurchaseOrderIssuePreparation(context)).object
  assert.equal(saved.purchaseOrderIssued, false)
  assert.equal(saved.supplierSent, false)
  assert.equal(saved.goodsReceived, false)
  assert.equal(saved.inventoryPosted, false)
  assert.equal(saved.invoiceCreated, false)
  assert.equal(saved.paymentCreated, false)
})
