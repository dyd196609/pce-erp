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
import { createPurchaseOrderIssueBoundaryContext, evaluatePurchaseOrderIssueBoundary,
  savePurchaseOrderIssueDecision } from '../../src/meta/runtime/purchaseOrderIssueBoundaryRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { createPurchaseOrderIssueBoundaryProcessAcceptanceDefinition,
  PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS006_STEPS, runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough,
  validatePurchaseOrderIssueBoundaryProcessAcceptance } from '../../src/meta/process/scm/purchaseOrderIssueBoundary/purchaseOrderIssueBoundaryProcessAcceptanceProfile.js'
import { validateIssuePreparationBoundaryHandoff } from '../../src/meta/process/scm/purchaseOrderIssueBoundary/purchaseOrderIssuePreparationBoundaryHandoffContract.js'

let sequence = 0

function issueBoundaryChain(inquiryNo) {
  const quotes = ['A', 'B'].map((suffix, index) => ({
    quoteNo: `SQ-POIB-${suffix}-${sequence}`, inquiryNo, supplierId: `SUP-POIB-${suffix}`,
    supplierName: `Supplier ${suffix}`, currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
    lines: [{ materialCode: 'MAT-POIB-001', materialName: 'Issue Boundary Material', quantity: 10,
      unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }],
  }))
  const comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(
    generateQuoteComparisonFact(createQuoteComparisonContext(quotes))).object)
  const recommendation = markSupplierRecommendationApprovalReady(saveSupplierRecommendationDecision(
    generateSupplierRecommendationDecision(createSupplierRecommendationContext(comparison))).object)
  const gateDecision = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(
    createPurchaseOrderCreationGateContext(recommendation))).object
  const transaction = createPurchaseOrderTransaction(createPurchaseOrderTransactionContext(gateDecision))
  const issueContext = createPurchaseOrderIssuePreparationContext(transaction)
  const preparation = savePurchaseOrderIssuePreparation(checkPurchaseOrderIssuePreparation(issueContext)).object
  return { quotes, comparison, recommendation, gateDecision, transaction, preparation }
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() { sequence += 1; artifacts.request = { requestNo: `PR-POIB-${sequence}` }; return artifacts.request },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { inquiryNo: `PI-POIB-${sequence}`, sourceRequestNo: request.requestNo }; return artifacts.inquiry
    },
    async loadSupplierQuotes(inquiry) {
      artifacts.chain = issueBoundaryChain(inquiry.inquiryNo); artifacts.quotes = artifacts.chain.quotes; return artifacts.quotes
    },
    async loadQuoteComparison() { artifacts.comparison = artifacts.chain.comparison; return artifacts.comparison },
    async loadSupplierRecommendation() { artifacts.recommendation = artifacts.chain.recommendation; return artifacts.recommendation },
    async loadPurchaseOrderGateDecision() { artifacts.gateDecision = artifacts.chain.gateDecision; return artifacts.gateDecision },
    async loadPurchaseOrderTransaction() { artifacts.transaction = artifacts.chain.transaction; return artifacts.transaction },
    async loadIssuePreparation() { artifacts.preparation = artifacts.chain.preparation; return artifacts.preparation },
    async createIssueBoundaryContext(preparation) {
      artifacts.context = createPurchaseOrderIssueBoundaryContext(preparation); return artifacts.context
    },
    async evaluateIssuePermission(context) {
      artifacts.decision = evaluatePurchaseOrderIssueBoundary(context); return artifacts.decision
    },
    async saveIssueDecision(decision) {
      const result = savePurchaseOrderIssueDecision(decision); artifacts.decision = result.object; return result
    },
  }
}

test('PROCESS-006 executes purchase request through purchase order issue boundary', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS006_STEPS)
  assert.equal(artifacts.decision.status, 'allowed')
})

test('IssueBoundary profile passes all acceptance families', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validatePurchaseOrderIssueBoundaryProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('preparation handoff transfers supplier, order, result, source chain and evidence', () => {
  sequence += 1
  const { preparation } = issueBoundaryChain(`PI-POIB-HANDOFF-${sequence}`)
  const context = createPurchaseOrderIssueBoundaryContext(preparation)
  const validation = validateIssuePreparationBoundaryHandoff(preparation, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields,
    ['supplier', 'orderInformation', 'preparationResult', 'sourceChain', 'evidence'])
})

test('three Action Contracts close the allowed state path', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createPurchaseOrderIssueBoundaryProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_ISSUE_BOUNDARY_CONTEXT').context
  context = executeProcessAction(definition, context, 'EVALUATE_ISSUE_PERMISSION').context
  context = executeProcessAction(definition, context, 'SAVE_ISSUE_DECISION').context
  assert.equal(context.state, 'allowed')
})

test('blocked preparation produces blocked issue permission decision', () => {
  sequence += 1
  const { preparation } = issueBoundaryChain(`PI-POIB-BLOCK-${sequence}`)
  const blockedPreparation = { ...preparation, preparationNo: `${preparation.preparationNo}-BLOCK`,
    status: 'blocked', ready: false, blockedReasons: ['POIP-DELIVERY-REQUIREMENTS'],
    checks: preparation.checks.map((item, index) => index === 0 ? { ...item, passed: false } : item) }
  const context = createPurchaseOrderIssueBoundaryContext(blockedPreparation)
  const saved = savePurchaseOrderIssueDecision(evaluatePurchaseOrderIssueBoundary(context)).object
  assert.equal(saved.status, 'blocked')
  assert.ok(saved.blockedReasons.includes('POIB-PREPARATION-READY'))
})

test('allowed decision never issues, sends, receives, posts inventory, invoices or pays', () => {
  sequence += 1
  const { preparation } = issueBoundaryChain(`PI-POIB-BOUNDARY-${sequence}`)
  const context = createPurchaseOrderIssueBoundaryContext(preparation)
  const saved = savePurchaseOrderIssueDecision(evaluatePurchaseOrderIssueBoundary(context)).object
  assert.equal(saved.purchaseOrderIssued, false)
  assert.equal(saved.supplierSent, false)
  assert.equal(saved.goodsReceived, false)
  assert.equal(saved.inventoryPosted, false)
  assert.equal(saved.invoiceCreated, false)
  assert.equal(saved.paymentCreated, false)
})
