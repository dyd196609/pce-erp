import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createSupplierQuoteContext,
  markSupplierQuoteWaiting,
  receiveSupplierQuote,
  saveSupplierQuote,
} from '../../src/meta/runtime/supplierQuoteRuntime.js'
import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { resolveStateTransition } from '../../src/meta/process/contract/processStateTransitionContract.js'
import {
  createSupplierQuoteProcessAcceptanceDefinition,
  runSupplierQuoteEndToEndBusinessWalkthrough,
  SUPPLIER_QUOTE_PROCESS006_STEPS,
  validateSupplierQuoteProcessAcceptance,
} from '../../src/meta/process/scm/supplierQuote/supplierQuoteProcessAcceptanceProfile.js'
import { validatePurchaseInquirySupplierQuoteHandoff } from '../../src/meta/process/scm/supplierQuote/purchaseInquirySupplierQuoteHandoffContract.js'

let sequence = 0

function inquiryFixture() {
  sequence += 1
  return {
    inquiryNo: `PI-SQ-RUNTIME-${sequence}`,
    sourceRequestNo: `PR-SQ-RUNTIME-${sequence}`,
    statusCode: 'draft',
    responseDeadline: '2026-08-31',
    lines: [
      { lineNo: 1, materialCode: 'MAT-SQ-001', materialName: '报价验收物料', quantity: 5, unit: '件' },
    ],
    suppliers: [{ supplierId: 'SUP-SQ-001', supplierName: '候选供应商一' }],
  }
}

function walkthroughAdapters(artifacts) {
  return {
    async loadPurchaseRequest() {
      artifacts.request = { requestNo: `PR-SQ-PROCESS-${sequence + 1}` }
      return artifacts.request
    },
    async loadPurchaseInquiry(request) {
      artifacts.inquiry = { ...inquiryFixture(), sourceRequestNo: request.requestNo }
      return artifacts.inquiry
    },
    async createSupplierQuoteContext(inquiry) {
      artifacts.context = createSupplierQuoteContext(inquiry)
      return artifacts.context
    },
    async receiveSupplierQuote(context) {
      artifacts.waitingContext = markSupplierQuoteWaiting(context)
      artifacts.quote = receiveSupplierQuote(artifacts.waitingContext, {
        supplierId: 'SUP-SQ-001',
        quoteDate: '2026-08-04',
        currency: 'CNY',
        validUntil: '2026-08-31',
        lines: context.materials.map(item => ({ ...item, unitPrice: 25, taxRate: 13, deliveryDate: '2026-08-25' })),
      })
      return artifacts.quote
    },
    async saveSupplierQuote(quote) {
      const result = saveSupplierQuote(quote)
      artifacts.quote = result.object
      return result
    },
  }
}

test('PROCESS-006 executes purchase request, inquiry, quote context and quote receipt', async () => {
  const artifacts = {}
  const walkthrough = await runSupplierQuoteEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))

  assert.equal(walkthrough.result, 'PASS')
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), SUPPLIER_QUOTE_PROCESS006_STEPS)
  assert.equal(artifacts.quote.status, 'quotation_completed')
})

test('SupplierQuote profile passes all contracts, context, regression and PROCESS-006', async () => {
  const artifacts = {}
  const walkthrough = await runSupplierQuoteEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const acceptance = validateSupplierQuoteProcessAcceptance(walkthrough, artifacts)

  assert.equal(acceptance.status, 'SCM_SUPPLIER_QUOTE_RUNTIME_READY')
  assert.equal(acceptance.report.contracts.node.result, 'PASS')
  assert.equal(acceptance.report.contracts.context.result, 'PASS')
  for (const family of ['action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('PurchaseInquiry handoff transfers inquiry number, materials, quantity, candidates and deadline', () => {
  const inquiry = inquiryFixture()
  const context = createSupplierQuoteContext(inquiry)
  const validation = validatePurchaseInquirySupplierQuoteHandoff(inquiry, context)

  assert.equal(validation.result, 'PASS')
  assert.deepEqual(validation.transferredFields, ['inquiryNo', 'materials', 'quantity', 'supplierCandidates', 'deadline'])
  assert.equal(context.materials[0].quantity, inquiry.lines[0].quantity)
})

test('three Action Contracts and internal wait event reach quotation_completed', async () => {
  const artifacts = {}
  const walkthrough = await runSupplierQuoteEndToEndBusinessWalkthrough(walkthroughAdapters(artifacts))
  const definition = createSupplierQuoteProcessAcceptanceDefinition(walkthrough)
  const stateModel = definition.stateModels[0]
  let context = definition.contexts[0]

  context = executeProcessAction(definition, context, 'CREATE_SUPPLIER_QUOTE_CONTEXT').context
  const wait = resolveStateTransition(stateModel, context.state, 'WAIT_FOR_SUPPLIER_QUOTE')
  context = { ...context, state: wait.to }
  context = executeProcessAction(definition, context, 'RECEIVE_SUPPLIER_QUOTE').context
  context = executeProcessAction(definition, context, 'SAVE_SUPPLIER_QUOTE').context
  assert.equal(context.state, 'quotation_completed')
})

test('runtime blocks non-candidate suppliers and preserves prohibited boundaries', () => {
  const context = markSupplierQuoteWaiting(createSupplierQuoteContext(inquiryFixture()))
  assert.throws(() => receiveSupplierQuote(context, { supplierId: 'SUP-NOT-CANDIDATE', lines: context.materials }), /不在候选范围/)
  assert.equal(context.supplierApiCalled, false)
  assert.equal(context.quoteComparisonCreated, false)
  assert.equal(context.purchaseOrderCreated, false)
  assert.equal(context.paymentCreated, false)
})

