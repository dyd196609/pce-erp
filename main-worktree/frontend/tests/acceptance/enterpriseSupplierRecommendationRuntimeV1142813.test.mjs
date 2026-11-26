import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createQuoteComparisonContext,
  generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady,
  saveQuoteComparison,
} from '../../src/meta/runtime/quoteComparisonRuntime.js'
import {
  createSupplierRecommendationContext,
  generateSupplierRecommendationDecision,
  markSupplierRecommendationApprovalReady,
  saveSupplierRecommendationDecision,
} from '../../src/meta/runtime/supplierRecommendationRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { resolveStateTransition } from '../../src/meta/process/contract/processStateTransitionContract.js'
import {
  createSupplierRecommendationProcessAcceptanceDefinition,
  runSupplierRecommendationEndToEndBusinessWalkthrough,
  SUPPLIER_RECOMMENDATION_PROCESS006_STEPS,
  validateSupplierRecommendationProcessAcceptance,
} from '../../src/meta/process/scm/supplierRecommendation/supplierRecommendationProcessAcceptanceProfile.js'
import { validateQuoteComparisonRecommendationHandoff } from '../../src/meta/process/scm/supplierRecommendation/quoteComparisonRecommendationHandoffContract.js'

let sequence = 0

function quoteFixtures(inquiryNo) {
  return [
    { quoteNo: `SQ-SR-A-${sequence}`, inquiryNo, supplierId: 'SUP-SR-A', supplierName: 'Supplier A', currency: 'CNY',
      validUntil: '2026-09-30', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-SR-001', materialName: 'Recommendation Material', quantity: 10, unit: 'EA', unitPrice: 80, deliveryDate: '2026-08-25' }] },
    { quoteNo: `SQ-SR-B-${sequence}`, inquiryNo, supplierId: 'SUP-SR-B', supplierName: 'Supplier B', currency: 'CNY',
      validUntil: '2026-09-30', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-SR-001', materialName: 'Recommendation Material', quantity: 10, unit: 'EA', unitPrice: 90, deliveryDate: '2026-08-20' }] },
  ]
}

function completedComparison(quotes) {
  const context = createQuoteComparisonContext(quotes)
  const comparing = generateQuoteComparisonFact(context)
  return markQuoteComparisonRecommendationReady(saveQuoteComparison(comparing).object)
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      sequence += 1
      artifacts.request = { requestNo: `PR-SR-PROCESS-${sequence}` }
      return artifacts.request
    },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { inquiryNo: `PI-SR-PROCESS-${sequence}`, sourceRequestNo: request.requestNo }
      return artifacts.inquiry
    },
    async loadSupplierQuotes(inquiry) {
      artifacts.quotes = quoteFixtures(inquiry.inquiryNo)
      return artifacts.quotes
    },
    async loadQuoteComparison(quotes) {
      artifacts.comparison = completedComparison(quotes)
      return artifacts.comparison
    },
    async createRecommendationContext(comparison) {
      artifacts.context = createSupplierRecommendationContext(comparison)
      return artifacts.context
    },
    async generateRecommendationDecision(context) {
      artifacts.decision = generateSupplierRecommendationDecision(context)
      return artifacts.decision
    },
    async saveRecommendationDecision(decision) {
      const result = saveSupplierRecommendationDecision(decision)
      artifacts.decision = result.object
      return result
    },
  }
}

test('PROCESS-006 executes purchase request through supplier recommendation decision', async () => {
  const artifacts = {}
  const walkthrough = await runSupplierRecommendationEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), SUPPLIER_RECOMMENDATION_PROCESS006_STEPS)
  assert.equal(artifacts.decision.status, 'recommendation_completed')
})

test('SupplierRecommendation profile passes contracts, context and protected boundaries', async () => {
  const artifacts = {}
  const walkthrough = await runSupplierRecommendationEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validateSupplierRecommendationProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_SUPPLIER_RECOMMENDATION_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('QuoteComparison handoff transfers result, supplier, price, delivery and risk evidence', () => {
  sequence += 1
  const comparison = completedComparison(quoteFixtures(`PI-SR-HANDOFF-${sequence}`))
  const context = createSupplierRecommendationContext(comparison)
  const validation = validateQuoteComparisonRecommendationHandoff(comparison, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields,
    ['comparisonResult', 'suppliers', 'priceEvidence', 'deliveryEvidence', 'riskEvidence'])
})

test('recommendation rules create an explainable supplier decision', () => {
  sequence += 1
  const comparison = completedComparison(quoteFixtures(`PI-SR-RULE-${sequence}`))
  const decision = generateSupplierRecommendationDecision(createSupplierRecommendationContext(comparison))
  assert.equal(decision.recommendedSupplierId, 'SUP-SR-A')
  assert.deepEqual(decision.decisionBasis, ['SR-PRICE-EVIDENCE', 'SR-DELIVERY-EVIDENCE', 'SR-VALIDITY-EVIDENCE'])
  assert.equal(decision.evaluations.length, 2)
})

test('three Action Contracts and internal ready event close the state path', async () => {
  const artifacts = {}
  const walkthrough = await runSupplierRecommendationEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createSupplierRecommendationProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_RECOMMENDATION_CONTEXT').context
  context = executeProcessAction(definition, context, 'GENERATE_RECOMMENDATION_DECISION').context
  context = executeProcessAction(definition, context, 'SAVE_RECOMMENDATION_DECISION').context
  assert.equal(context.state, 'recommendation_completed')
  assert.equal(resolveStateTransition(definition.stateModels[0], context.state, 'MARK_APPROVAL_READY').to, 'approval_ready')
})

test('approval_ready does not create order, submit approval or create payment', () => {
  sequence += 1
  const comparison = completedComparison(quoteFixtures(`PI-SR-BOUNDARY-${sequence}`))
  const context = createSupplierRecommendationContext(comparison)
  const decision = generateSupplierRecommendationDecision(context)
  const ready = markSupplierRecommendationApprovalReady(saveSupplierRecommendationDecision(decision).object)
  assert.equal(ready.status, 'approval_ready')
  assert.equal(ready.purchaseOrderCreated, false)
  assert.equal(ready.approvalSubmitted, false)
  assert.equal(ready.paymentCreated, false)
})
