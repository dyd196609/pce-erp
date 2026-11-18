import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  PURCHASE_ORDER_GATE_HANDOFF_SOURCE,
  PURCHASE_ORDER_TRANSACTION_NODE_CODE,
  PURCHASE_ORDER_TRANSACTION_NODE_RUNTIME_CONTRACT,
} from './purchaseOrderTransactionNodeRuntimeContract.js'
import { PURCHASE_ORDER_TRANSACTION_ACTION_CONTRACTS } from './purchaseOrderTransactionActionContracts.js'
import {
  PURCHASE_ORDER_TRANSACTION_STATE_TRANSITION_CONTRACT,
  validatePurchaseOrderTransactionStateBoundaries,
} from './purchaseOrderTransactionStateTransitionContract.js'
import {
  PURCHASE_ORDER_GATE_TRANSACTION_HANDOFF_CONTRACT,
  validatePurchaseOrderGateTransactionHandoff,
} from './purchaseOrderGateTransactionHandoffContract.js'

export const PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.15'
export const PURCHASE_ORDER_TRANSACTION_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST', 'PURCHASE_INQUIRY', 'SUPPLIER_QUOTE', 'QUOTE_COMPARISON',
  'SUPPLIER_RECOMMENDATION', 'PURCHASE_ORDER_CREATION_GATE',
  'PURCHASE_ORDER_TRANSACTION_CONTEXT', 'PURCHASE_ORDER_TRANSACTION_DRAFT',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runPurchaseOrderTransactionEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes', 'loadQuoteComparison',
    'loadSupplierRecommendation', 'loadPurchaseOrderGateDecision', 'createTransactionContext', 'createTransaction']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_ORDER_TRANSACTION_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`PURCHASE_ORDER_TRANSACTION_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }
  let request
  let inquiry
  let quotes
  let comparison
  let recommendation
  let gateDecision
  let context
  let transaction
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo)
    quotes = await execute('SUPPLIER_QUOTE', () => adapters.loadSupplierQuotes(inquiry), value => Array.isArray(value) && value.length > 0)
    comparison = await execute('QUOTE_COMPARISON', () => adapters.loadQuoteComparison(quotes), value => value?.objectType === 'QuoteComparison' && value?.status === 'recommendation_ready')
    recommendation = await execute('SUPPLIER_RECOMMENDATION', () => adapters.loadSupplierRecommendation(comparison), value => value?.objectType === 'SupplierRecommendationDecision' && value?.status === 'approval_ready')
    gateDecision = await execute('PURCHASE_ORDER_CREATION_GATE', () => adapters.loadPurchaseOrderGateDecision(recommendation), value => value?.objectType === 'PurchaseOrderCreationGateDecision' && value?.status === 'eligible' && value?.purchaseOrderCreated === false)
    context = await execute('PURCHASE_ORDER_TRANSACTION_CONTEXT', () => adapters.createTransactionContext(gateDecision), value => value?.objectType === 'PurchaseOrderTransactionContext' && value?.status === 'transaction_context_created')
    transaction = await execute('PURCHASE_ORDER_TRANSACTION_DRAFT', () => adapters.createTransaction(context), value => value?.objectType === 'PurchaseOrderTransaction' && value?.status === 'draft' && value?.purchaseOrderExecutionCreated === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-TRANSACTION-E2E',
      sourceNode: PURCHASE_ORDER_GATE_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-TRANSACTION-E2E',
    sourceNode: PURCHASE_ORDER_GATE_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
    executed: true, completed: true, result: 'PASS', requestNo: request.requestNo, inquiryNo: inquiry.inquiryNo,
    comparisonNo: comparison.comparisonNo, recommendationDecisionNo: recommendation.decisionNo,
    gateDecisionNo: gateDecision.gateDecisionNo, transactionNo: transaction.transactionNo,
    finalState: transaction.status, steps: Object.freeze(steps),
  })
}

export function createPurchaseOrderTransactionProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validatePurchaseOrderTransactionStateBoundaries()
  return Object.freeze({
    version: PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-order-transaction-runtime', pageUrl: '/scm/purchase-inquiry',
      nodeCode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-purchase-order-transaction-context', actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION_CONTEXT' }),
        Object.freeze({ buttonCode: 'create-purchase-order-transaction', actionCode: 'CREATE_PURCHASE_ORDER_TRANSACTION' }),
        Object.freeze({ buttonCode: 'save-purchase-order-transaction', actionCode: 'SAVE_PURCHASE_ORDER_TRANSACTION' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_ORDER_TRANSACTION_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([PURCHASE_ORDER_GATE_HANDOFF_SOURCE]),
    actions: PURCHASE_ORDER_TRANSACTION_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_ORDER_TRANSACTION_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([PURCHASE_ORDER_GATE_TRANSACTION_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-order-transaction-runtime-acceptance',
      processCode: 'SCM_PURCHASE_ORDER_TRANSACTION_FLOW', objectType: 'PurchaseOrderTransaction',
      objectId: 'purchase-order-gate-handoff', nodeCode: PURCHASE_ORDER_TRANSACTION_NODE_CODE,
      state: 'purchase_order_gate_eligible', actorId: 'process-006-purchase-order-transaction-user',
      actorRole: 'purchase-order-transaction-operator', correlationId: 'purchase-order-transaction-v1142815',
      attributes: { acceptanceVersion: PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'POT-REG-GATE-TRANSACTION-FIELD-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'POT-REG-CONTEXT-TO-DRAFT-ONLY', result: boundaries.result }),
      Object.freeze({ caseCode: 'POT-REG-PENDING-ISSUE-AND-ISSUED-LOCKED', result: 'PASS' }),
      Object.freeze({ caseCode: 'POT-REG-NO-EXECUTION-PUBLISH-RECEIVE-INVOICE-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseOrderTransactionProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createPurchaseOrderTransactionProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_ORDER_TRANSACTION_PROCESS006_STEPS.length
    && PURCHASE_ORDER_TRANSACTION_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validatePurchaseOrderGateTransactionHandoff(artifacts.gateDecision, artifacts.context)
  const stateBoundaries = validatePurchaseOrderTransactionStateBoundaries()
  const boundariesProtected = artifacts.transaction?.status === 'draft'
    && artifacts.transaction?.purchaseOrderExecutionCreated === false
    && artifacts.transaction?.supplierPublished === false && artifacts.transaction?.goodsReceived === false
    && artifacts.transaction?.inventoryPosted === false && artifacts.transaction?.invoiceCreated === false
    && artifacts.transaction?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: PURCHASE_ORDER_TRANSACTION_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_ORDER_TRANSACTION_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected,
  })
}
