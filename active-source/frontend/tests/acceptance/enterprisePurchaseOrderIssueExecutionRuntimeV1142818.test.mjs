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
import { createPurchaseOrderIssueExecutionContext, checkPurchaseOrderIssueExecution,
  savePurchaseOrderIssueExecutionPreparation } from '../../src/meta/runtime/purchaseOrderIssueExecutionRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { createPurchaseOrderIssueExecutionProcessAcceptanceDefinition,
  PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS006_STEPS, runPurchaseOrderIssueExecutionEndToEndBusinessWalkthrough,
  validatePurchaseOrderIssueExecutionProcessAcceptance } from '../../src/meta/process/scm/purchaseOrderIssueExecution/purchaseOrderIssueExecutionProcessAcceptanceProfile.js'
import { validateIssueBoundaryExecutionHandoff } from '../../src/meta/process/scm/purchaseOrderIssueExecution/purchaseOrderIssueBoundaryExecutionHandoffContract.js'

let sequence = 0

function executionChain(inquiryNo) {
  const quotes = ['A', 'B'].map((suffix, index) => ({
    quoteNo: `SQ-POIE-${suffix}-${sequence}`, inquiryNo, supplierId: `SUP-POIE-${suffix}`,
    supplierName: `Supplier ${suffix}`, currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
    lines: [{ materialCode: 'MAT-POIE-001', materialName: 'Execution Authorization Material', quantity: 10,
      unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }],
  }))
  const comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(
    generateQuoteComparisonFact(createQuoteComparisonContext(quotes))).object)
  const recommendation = markSupplierRecommendationApprovalReady(saveSupplierRecommendationDecision(
    generateSupplierRecommendationDecision(createSupplierRecommendationContext(comparison))).object)
  const gateDecision = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(
    createPurchaseOrderCreationGateContext(recommendation))).object
  const transaction = createPurchaseOrderTransaction(createPurchaseOrderTransactionContext(gateDecision))
  const preparation = savePurchaseOrderIssuePreparation(checkPurchaseOrderIssuePreparation(
    createPurchaseOrderIssuePreparationContext(transaction))).object
  const issueDecision = savePurchaseOrderIssueDecision(evaluatePurchaseOrderIssueBoundary(
    createPurchaseOrderIssueBoundaryContext(preparation))).object
  return { quotes, comparison, recommendation, gateDecision, transaction, preparation, issueDecision }
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() { sequence += 1; artifacts.request = { requestNo: `PR-POIE-${sequence}` }; return artifacts.request },
    async loadPurchaseInquiry(request) { artifacts.inquiry = { inquiryNo: `PI-POIE-${sequence}`, sourceRequestNo: request.requestNo }; return artifacts.inquiry },
    async loadSupplierQuotes(inquiry) { artifacts.chain = executionChain(inquiry.inquiryNo); artifacts.quotes = artifacts.chain.quotes; return artifacts.quotes },
    async loadQuoteComparison() { artifacts.comparison = artifacts.chain.comparison; return artifacts.comparison },
    async loadSupplierRecommendation() { artifacts.recommendation = artifacts.chain.recommendation; return artifacts.recommendation },
    async loadPurchaseOrderGateDecision() { artifacts.gateDecision = artifacts.chain.gateDecision; return artifacts.gateDecision },
    async loadPurchaseOrderTransaction() { artifacts.transaction = artifacts.chain.transaction; return artifacts.transaction },
    async loadIssuePreparation() { artifacts.preparation = artifacts.chain.preparation; return artifacts.preparation },
    async loadIssueDecision() { artifacts.issueDecision = artifacts.chain.issueDecision; return artifacts.issueDecision },
    async createIssueExecutionContext(issueDecision) {
      artifacts.context = createPurchaseOrderIssueExecutionContext(issueDecision); return artifacts.context
    },
    async checkExecutionAuthorization(context) {
      artifacts.authorization = checkPurchaseOrderIssueExecution(context); return artifacts.authorization
    },
    async saveExecutionPreparation(authorization) {
      const result = savePurchaseOrderIssueExecutionPreparation(authorization); artifacts.authorization = result.object; return result
    },
  }
}

test('PROCESS-006 executes purchase request through issue execution authorization preparation', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssueExecutionEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS006_STEPS)
  assert.equal(artifacts.authorization.status, 'authorized')
})

test('IssueExecution profile passes every acceptance family', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssueExecutionEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validatePurchaseOrderIssueExecutionProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_PURCHASE_ORDER_ISSUE_EXECUTION_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('boundary handoff transfers order, supplier, authorization evidence and source chain', () => {
  sequence += 1
  const { issueDecision } = executionChain(`PI-POIE-HANDOFF-${sequence}`)
  const context = createPurchaseOrderIssueExecutionContext(issueDecision)
  const validation = validateIssueBoundaryExecutionHandoff(issueDecision, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields,
    ['orderInformation', 'supplierInformation', 'authorizationEvidence', 'sourceChain'])
})

test('three Action Contracts close the authorized state path', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderIssueExecutionEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createPurchaseOrderIssueExecutionProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_ISSUE_EXECUTION_CONTEXT').context
  context = executeProcessAction(definition, context, 'CHECK_EXECUTION_AUTHORIZATION').context
  context = executeProcessAction(definition, context, 'SAVE_EXECUTION_PREPARATION').context
  assert.equal(context.state, 'authorized')
})

test('blocked issue decision creates blocked authorization preparation', () => {
  sequence += 1
  const { issueDecision } = executionChain(`PI-POIE-BLOCK-${sequence}`)
  const blockedDecision = { ...issueDecision, issueDecisionNo: `${issueDecision.issueDecisionNo}-BLOCK`,
    status: 'blocked', issuePermissionGranted: false,
    checks: issueDecision.checks.map((item, index) => index === 0 ? { ...item, passed: false } : item) }
  const context = createPurchaseOrderIssueExecutionContext(blockedDecision)
  const saved = savePurchaseOrderIssueExecutionPreparation(checkPurchaseOrderIssueExecution(context)).object
  assert.equal(saved.status, 'blocked')
  assert.ok(saved.blockedReasons.includes('POIE-BOUNDARY-ALLOWED'))
})

test('authorized preparation calls no API and performs no issue or downstream action', () => {
  sequence += 1
  const { issueDecision } = executionChain(`PI-POIE-BOUNDARY-${sequence}`)
  const context = createPurchaseOrderIssueExecutionContext(issueDecision)
  const saved = savePurchaseOrderIssueExecutionPreparation(checkPurchaseOrderIssueExecution(context)).object
  assert.equal(saved.supplierApiCalled, false)
  assert.equal(saved.purchaseOrderIssued, false)
  assert.equal(saved.supplierSent, false)
  assert.equal(saved.goodsReceived, false)
  assert.equal(saved.inventoryPosted, false)
  assert.equal(saved.invoiceCreated, false)
  assert.equal(saved.paymentCreated, false)
})
