import test from 'node:test'
import assert from 'node:assert/strict'

import { createQuoteComparisonContext, generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady, saveQuoteComparison } from '../../src/meta/runtime/quoteComparisonRuntime.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision,
  markSupplierRecommendationApprovalReady, saveSupplierRecommendationDecision } from '../../src/meta/runtime/supplierRecommendationRuntime.js'
import { createPurchaseOrderCreationGateContext, evaluatePurchaseOrderGateDecision,
  savePurchaseOrderGateDecision } from '../../src/meta/runtime/purchaseOrderCreationGateRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { resolveStateTransition } from '../../src/meta/process/contract/processStateTransitionContract.js'
import { createPurchaseOrderCreationGateProcessAcceptanceDefinition,
  PURCHASE_ORDER_CREATION_GATE_PROCESS006_STEPS, runPurchaseOrderCreationGateEndToEndBusinessWalkthrough,
  validatePurchaseOrderCreationGateProcessAcceptance } from '../../src/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationGateProcessAcceptanceProfile.js'
import { validateSupplierRecommendationPurchaseOrderGateHandoff } from '../../src/meta/process/scm/purchaseOrderCreationGate/supplierRecommendationPurchaseOrderGateHandoffContract.js'

let sequence = 0

function quoteFixtures(inquiryNo, blocked = false) {
  return ['A', 'B'].map((suffix, index) => ({
    quoteNo: `SQ-POG-${suffix}-${sequence}`, inquiryNo, supplierId: `SUP-POG-${suffix}`,
    supplierName: `Supplier ${suffix}`, currency: 'CNY',
    validUntil: blocked && index === 0 ? '2026-08-01' : '2026-09-30', status: 'quotation_completed',
    lines: [{ materialCode: 'MAT-POG-001', materialName: 'Gate Material', quantity: 10,
      unit: 'EA', unitPrice: 80 + index * 10, deliveryDate: `2026-08-${25 - index * 5}` }],
  }))
}

function recommendationFixture(inquiryNo, blocked = false) {
  const quotes = quoteFixtures(inquiryNo, blocked)
  const comparisonContext = createQuoteComparisonContext(quotes)
  const comparison = markQuoteComparisonRecommendationReady(
    saveQuoteComparison(generateQuoteComparisonFact(comparisonContext)).object)
  const recommendationContext = createSupplierRecommendationContext(comparison)
  const recommendation = markSupplierRecommendationApprovalReady(
    saveSupplierRecommendationDecision(generateSupplierRecommendationDecision(recommendationContext)).object)
  return { quotes, comparison, recommendation }
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      sequence += 1
      artifacts.request = { requestNo: `PR-POG-PROCESS-${sequence}` }
      return artifacts.request
    },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { inquiryNo: `PI-POG-PROCESS-${sequence}`, sourceRequestNo: request.requestNo }
      return artifacts.inquiry
    },
    async loadSupplierQuotes(inquiry) {
      artifacts.chain = recommendationFixture(inquiry.inquiryNo)
      artifacts.quotes = artifacts.chain.quotes
      return artifacts.quotes
    },
    async loadQuoteComparison() {
      artifacts.comparison = artifacts.chain.comparison
      return artifacts.comparison
    },
    async loadSupplierRecommendation() {
      artifacts.recommendation = artifacts.chain.recommendation
      return artifacts.recommendation
    },
    async createGateContext(recommendation) {
      artifacts.context = createPurchaseOrderCreationGateContext(recommendation)
      return artifacts.context
    },
    async evaluateEligibility(context) {
      artifacts.decision = evaluatePurchaseOrderGateDecision(context)
      return artifacts.decision
    },
    async saveGateDecision(decision) {
      const result = savePurchaseOrderGateDecision(decision)
      artifacts.decision = result.object
      return result
    },
  }
}

test('PROCESS-006 executes purchase request through purchase order creation gate', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderCreationGateEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_ORDER_CREATION_GATE_PROCESS006_STEPS)
  assert.equal(artifacts.decision.status, 'eligible')
})

test('PurchaseOrderCreationGate profile passes all acceptance families', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderCreationGateEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validatePurchaseOrderCreationGateProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_PURCHASE_ORDER_CREATION_GATE_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('recommendation handoff transfers supplier, evidence, cost and source chain', () => {
  sequence += 1
  const { recommendation } = recommendationFixture(`PI-POG-HANDOFF-${sequence}`)
  const context = createPurchaseOrderCreationGateContext(recommendation)
  const validation = validateSupplierRecommendationPurchaseOrderGateHandoff(recommendation, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields,
    ['recommendedSupplier', 'recommendationEvidence', 'comparisonEvidence', 'costReference', 'sourceChain'])
})

test('three Action Contracts close the eligible state path', async () => {
  const artifacts = {}
  const walkthrough = await runPurchaseOrderCreationGateEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createPurchaseOrderCreationGateProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_PURCHASE_ORDER_GATE_CONTEXT').context
  context = executeProcessAction(definition, context, 'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY').context
  context = executeProcessAction(definition, context, 'SAVE_PURCHASE_ORDER_GATE_DECISION').context
  assert.equal(context.state, 'eligible')
})

test('blocking risk produces blocked decision through controlled state branch', () => {
  sequence += 1
  const { recommendation } = recommendationFixture(`PI-POG-BLOCK-${sequence}`, true)
  const context = createPurchaseOrderCreationGateContext(recommendation)
  const decision = evaluatePurchaseOrderGateDecision(context)
  const saved = savePurchaseOrderGateDecision(decision).object
  assert.equal(saved.status, 'blocked')
  assert.ok(saved.blockedReasons.includes('PO-GATE-NO-BLOCKING-RISK'))
  assert.equal(resolveStateTransition(PURCHASE_ORDER_CREATION_GATE_STATE_MODEL(), 'evaluating', 'BLOCK_PURCHASE_ORDER_CREATION').to, 'blocked')
})

test('eligible decision never creates order, publishes supplier or creates payment', () => {
  sequence += 1
  const { recommendation } = recommendationFixture(`PI-POG-BOUNDARY-${sequence}`)
  const context = createPurchaseOrderCreationGateContext(recommendation)
  const saved = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(context)).object
  assert.equal(saved.status, 'eligible')
  assert.equal(saved.purchaseOrderCreated, false)
  assert.equal(saved.supplierPublished, false)
  assert.equal(saved.paymentCreated, false)
})

function PURCHASE_ORDER_CREATION_GATE_STATE_MODEL() {
  return createPurchaseOrderCreationGateProcessAcceptanceDefinition({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'state-only', sourceNode: 'source', targetNode: 'target',
    executed: true, completed: true, result: 'PASS', steps: [{ sequence: 1, stepCode: 'STATE', result: 'PASS', evidence: 'state' }],
  }).stateModels[0]
}
