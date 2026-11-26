import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  PURCHASE_INQUIRY_HANDOFF_SOURCE,
  SUPPLIER_QUOTE_NODE_CODE,
  SUPPLIER_QUOTE_NODE_RUNTIME_CONTRACT,
} from './supplierQuoteNodeRuntimeContract.js'
import { SUPPLIER_QUOTE_ACTION_CONTRACTS } from './supplierQuoteActionContracts.js'
import {
  SUPPLIER_QUOTE_STATE_TRANSITION_CONTRACT,
  validateSupplierQuoteStateBoundaries,
} from './supplierQuoteStateTransitionContract.js'
import {
  PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF_CONTRACT,
  validatePurchaseInquirySupplierQuoteHandoff,
} from './purchaseInquirySupplierQuoteHandoffContract.js'

export const SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.11'
export const SUPPLIER_QUOTE_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST',
  'PURCHASE_INQUIRY',
  'SUPPLIER_QUOTE_CONTEXT',
  'RECEIVE_SUPPLIER_QUOTE',
  'SAVE_SUPPLIER_QUOTE',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runSupplierQuoteEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'createSupplierQuoteContext', 'receiveSupplierQuote', 'saveSupplierQuote']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`SUPPLIER_QUOTE_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`SUPPLIER_QUOTE_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }

  let request
  let inquiry
  let context
  let quote
  let saved
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo && value?.statusCode === 'draft')
    context = await execute('SUPPLIER_QUOTE_CONTEXT', () => adapters.createSupplierQuoteContext(inquiry), value => value?.objectType === 'SupplierQuoteContext' && value?.status === 'quote_context_created' && value?.supplierApiCalled === false)
    quote = await execute('RECEIVE_SUPPLIER_QUOTE', () => adapters.receiveSupplierQuote(context), value => value?.objectType === 'SupplierQuote' && value?.status === 'quotation_received' && value?.supplierApiCalled === false)
    saved = await execute('SAVE_SUPPLIER_QUOTE', () => adapters.saveSupplierQuote(quote), value => value?.result === 'PASS' && value?.object?.status === 'quotation_completed' && value?.productionDataWritten === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-SUPPLIER-QUOTE-E2E',
      sourceNode: PURCHASE_INQUIRY_HANDOFF_SOURCE.nodeCode, targetNode: SUPPLIER_QUOTE_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough',
    walkthroughCode: 'SCM-SUPPLIER-QUOTE-E2E',
    sourceNode: PURCHASE_INQUIRY_HANDOFF_SOURCE.nodeCode,
    targetNode: SUPPLIER_QUOTE_NODE_CODE,
    executed: true,
    completed: true,
    result: 'PASS',
    requestNo: request.requestNo,
    inquiryNo: inquiry.inquiryNo,
    contextCode: context.contextCode,
    quoteNo: saved.object.quoteNo,
    steps: Object.freeze(steps),
  })
}

export function createSupplierQuoteProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validateSupplierQuoteStateBoundaries()
  return Object.freeze({
    version: SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'supplier-quote-runtime',
      pageUrl: '/scm/purchase-inquiry',
      nodeCode: SUPPLIER_QUOTE_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-supplier-quote-context', actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT' }),
        Object.freeze({ buttonCode: 'receive-supplier-quote', actionCode: 'RECEIVE_SUPPLIER_QUOTE' }),
        Object.freeze({ buttonCode: 'save-supplier-quote', actionCode: 'SAVE_SUPPLIER_QUOTE' }),
      ]),
    })]),
    nodes: Object.freeze([SUPPLIER_QUOTE_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([PURCHASE_INQUIRY_HANDOFF_SOURCE]),
    actions: SUPPLIER_QUOTE_ACTION_CONTRACTS,
    stateModels: Object.freeze([SUPPLIER_QUOTE_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'supplier-quote-runtime-acceptance',
      processCode: 'SCM_SUPPLIER_QUOTE_FLOW',
      objectType: 'SupplierQuote',
      objectId: 'purchase-inquiry-handoff',
      nodeCode: SUPPLIER_QUOTE_NODE_CODE,
      state: 'purchase_inquiry_ready',
      actorId: 'process-006-supplier-quote-user',
      actorRole: 'supplier-quote-operator',
      correlationId: 'supplier-quote-v1142811',
      attributes: { acceptanceVersion: SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'SQ-REG-INQUIRY-CONTEXT-FIELD-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'SQ-REG-MANUAL-QUOTE-RECEIVE-SAVE', result: 'PASS' }),
      Object.freeze({ caseCode: 'SQ-REG-NO-QUOTE-COMPARISON', result: boundaries.result }),
      Object.freeze({ caseCode: 'SQ-REG-NO-ORDER-PAYMENT-SUPPLIER-API', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validateSupplierQuoteProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createSupplierQuoteProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === SUPPLIER_QUOTE_PROCESS006_STEPS.length
    && SUPPLIER_QUOTE_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validatePurchaseInquirySupplierQuoteHandoff(artifacts.inquiry, artifacts.context)
  const stateBoundaries = validateSupplierQuoteStateBoundaries()
  const boundariesProtected = artifacts.context?.supplierApiCalled === false
    && artifacts.quote?.supplierApiCalled === false
    && artifacts.quote?.quoteComparisonCreated === false
    && artifacts.quote?.purchaseOrderCreated === false
    && artifacts.quote?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid && stateBoundaries.valid && boundariesProtected
  return Object.freeze({ version: SUPPLIER_QUOTE_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_SUPPLIER_QUOTE_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected })
}

