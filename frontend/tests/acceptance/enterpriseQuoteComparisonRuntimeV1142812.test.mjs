import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createQuoteComparisonContext,
  generateQuoteComparisonFact,
  markQuoteComparisonRecommendationReady,
  saveQuoteComparison,
} from '../../src/meta/runtime/quoteComparisonRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { resolveStateTransition } from '../../src/meta/process/contract/processStateTransitionContract.js'
import {
  createQuoteComparisonProcessAcceptanceDefinition,
  QUOTE_COMPARISON_PROCESS006_STEPS,
  runQuoteComparisonEndToEndBusinessWalkthrough,
  validateQuoteComparisonProcessAcceptance,
} from '../../src/meta/process/scm/quoteComparison/quoteComparisonProcessAcceptanceProfile.js'
import { validateSupplierQuoteComparisonHandoff } from '../../src/meta/process/scm/quoteComparison/supplierQuoteComparisonHandoffContract.js'

let sequence = 0

function quoteFixtures() {
  sequence += 1
  const inquiryNo = `PI-QC-RUNTIME-${sequence}`
  return [
    { objectType: 'SupplierQuote', quoteNo: `SQ-A-${sequence}`, inquiryNo, supplierId: 'SUP-QC-A', supplierName: 'Supplier A',
      currency: 'CNY', validUntil: '2026-09-30', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-QC-001', materialName: 'Comparison Material', quantity: 10, unit: 'EA', unitPrice: 80, deliveryDate: '2026-08-25' }] },
    { objectType: 'SupplierQuote', quoteNo: `SQ-B-${sequence}`, inquiryNo, supplierId: 'SUP-QC-B', supplierName: 'Supplier B',
      currency: 'CNY', validUntil: '2026-09-20', status: 'quotation_completed',
      lines: [{ materialCode: 'MAT-QC-001', materialName: 'Comparison Material', quantity: 10, unit: 'EA', unitPrice: 85, deliveryDate: '2026-08-20' }] },
  ]
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      artifacts.request = { requestNo: `PR-QC-PROCESS-${sequence + 1}` }
      return artifacts.request
    },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { inquiryNo: `PI-QC-PROCESS-${sequence + 1}`, sourceRequestNo: request.requestNo }
      return artifacts.inquiry
    },
    async loadSupplierQuotes(inquiry) {
      artifacts.quotes = quoteFixtures().map(item => ({ ...item, inquiryNo: inquiry.inquiryNo }))
      return artifacts.quotes
    },
    async createQuoteComparisonContext(quotes) {
      artifacts.context = createQuoteComparisonContext(quotes)
      return artifacts.context
    },
    async generateQuoteComparisonFact(context) {
      artifacts.comparison = generateQuoteComparisonFact(context)
      return artifacts.comparison
    },
    async saveQuoteComparison(comparison) {
      const result = saveQuoteComparison(comparison)
      artifacts.comparison = result.object
      return result
    },
  }
}

test('PROCESS-006 executes purchase request, inquiry, quote and quote comparison', async () => {
  const artifacts = {}
  const walkthrough = await runQuoteComparisonEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), QUOTE_COMPARISON_PROCESS006_STEPS)
  assert.equal(artifacts.comparison.status, 'comparison_completed')
})

test('QuoteComparison profile passes all contract families and boundaries', async () => {
  const artifacts = {}
  const walkthrough = await runQuoteComparisonEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validateQuoteComparisonProcessAcceptance(walkthrough, artifacts)
  assert.equal(acceptance.status, 'SCM_QUOTE_COMPARISON_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('SupplierQuote array handoff transfers all required comparison fields', () => {
  const quotes = quoteFixtures()
  const context = createQuoteComparisonContext(quotes)
  const validation = validateSupplierQuoteComparisonHandoff(quotes, context)
  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields, ['supplier', 'quote', 'materials', 'quantity', 'price', 'deliveryDate', 'validUntil'])
  assert.equal(context.quotes[0].materials[0].unitPrice, quotes[0].lines[0].unitPrice)
})

test('three Action Contracts reach comparison_completed and internal event reaches recommendation_ready', async () => {
  const artifacts = {}
  const walkthrough = await runQuoteComparisonEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createQuoteComparisonProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  context = executeProcessAction(definition, context, 'CREATE_QUOTE_COMPARISON_CONTEXT').context
  context = executeProcessAction(definition, context, 'GENERATE_QUOTE_COMPARISON_FACT').context
  context = executeProcessAction(definition, context, 'SAVE_QUOTE_COMPARISON').context
  assert.equal(context.state, 'comparison_completed')
  const ready = resolveStateTransition(definition.stateModels[0], context.state, 'MARK_RECOMMENDATION_READY')
  assert.equal(ready.to, 'recommendation_ready')
})

test('comparison facts do not create recommendation, purchase order or finance action', () => {
  const context = createQuoteComparisonContext(quoteFixtures())
  const comparison = generateQuoteComparisonFact(context)
  const completed = saveQuoteComparison(comparison).object
  const ready = markQuoteComparisonRecommendationReady(completed)
  assert.equal(ready.status, 'recommendation_ready')
  assert.equal(ready.recommendedSupplierId, null)
  assert.equal(ready.supplierRecommendationCreated, false)
  assert.equal(ready.purchaseOrderCreated, false)
  assert.equal(ready.financeActionExecuted, false)
})

test('runtime rejects incomplete quote facts', () => {
  const [quote] = quoteFixtures()
  const invalid = { ...quote, lines: [{ ...quote.lines[0], unitPrice: 0 }] }
  assert.throws(() => createQuoteComparisonContext([invalid]), /SUPPLIER_QUOTES_INCOMPLETE/)
})
