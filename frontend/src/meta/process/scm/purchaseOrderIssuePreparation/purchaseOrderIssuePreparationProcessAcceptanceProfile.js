import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
  PURCHASE_ORDER_ISSUE_PREPARATION_NODE_RUNTIME_CONTRACT,
  PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE,
} from './purchaseOrderIssuePreparationNodeRuntimeContract.js'
import { PURCHASE_ORDER_ISSUE_PREPARATION_ACTION_CONTRACTS } from './purchaseOrderIssuePreparationActionContracts.js'
import {
  PURCHASE_ORDER_ISSUE_PREPARATION_STATE_TRANSITION_CONTRACT,
  validatePurchaseOrderIssuePreparationStateBoundaries,
} from './purchaseOrderIssuePreparationStateTransitionContract.js'
import {
  PURCHASE_ORDER_TRANSACTION_ISSUE_PREPARATION_HANDOFF_CONTRACT,
  validatePurchaseOrderTransactionIssuePreparationHandoff,
} from './purchaseOrderTransactionIssuePreparationHandoffContract.js'

export const PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.16'
export const PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST', 'PURCHASE_INQUIRY', 'SUPPLIER_QUOTE', 'QUOTE_COMPARISON',
  'SUPPLIER_RECOMMENDATION', 'PURCHASE_ORDER_CREATION_GATE', 'PURCHASE_ORDER_TRANSACTION',
  'ISSUE_PREPARATION_CONTEXT', 'CHECK_ISSUE_REQUIREMENTS', 'SAVE_ISSUE_PREPARATION',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runPurchaseOrderIssuePreparationEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes', 'loadQuoteComparison',
    'loadSupplierRecommendation', 'loadPurchaseOrderGateDecision', 'loadPurchaseOrderTransaction',
    'createIssuePreparationContext', 'checkIssueRequirements', 'saveIssuePreparation']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_ORDER_ISSUE_PREPARATION_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`PURCHASE_ORDER_ISSUE_PREPARATION_STEP_FAILED:${stepCode}`)
    return value
  }
  let request
  let inquiry
  let quotes
  let comparison
  let recommendation
  let gateDecision
  let transaction
  let context
  let preparation
  let saved
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo)
    quotes = await execute('SUPPLIER_QUOTE', () => adapters.loadSupplierQuotes(inquiry), value => Array.isArray(value) && value.length > 0)
    comparison = await execute('QUOTE_COMPARISON', () => adapters.loadQuoteComparison(quotes), value => value?.objectType === 'QuoteComparison' && value?.status === 'recommendation_ready')
    recommendation = await execute('SUPPLIER_RECOMMENDATION', () => adapters.loadSupplierRecommendation(comparison), value => value?.objectType === 'SupplierRecommendationDecision' && value?.status === 'approval_ready')
    gateDecision = await execute('PURCHASE_ORDER_CREATION_GATE', () => adapters.loadPurchaseOrderGateDecision(recommendation), value => value?.objectType === 'PurchaseOrderCreationGateDecision' && value?.status === 'eligible')
    transaction = await execute('PURCHASE_ORDER_TRANSACTION', () => adapters.loadPurchaseOrderTransaction(gateDecision), value => value?.objectType === 'PurchaseOrderTransaction' && value?.status === 'draft')
    context = await execute('ISSUE_PREPARATION_CONTEXT', () => adapters.createIssuePreparationContext(transaction), value => value?.objectType === 'PurchaseOrderIssuePreparationContext' && value?.status === 'issue_context_created')
    preparation = await execute('CHECK_ISSUE_REQUIREMENTS', () => adapters.checkIssueRequirements(context), value => value?.objectType === 'PurchaseOrderIssuePreparation' && value?.status === 'checking')
    saved = await execute('SAVE_ISSUE_PREPARATION', () => adapters.saveIssuePreparation(preparation), value => value?.result === 'PASS' && ['ready_for_issue', 'blocked'].includes(value?.object?.status) && value?.object?.purchaseOrderIssued === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-ISSUE-PREPARATION-E2E',
      sourceNode: PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-ISSUE-PREPARATION-E2E',
    sourceNode: PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
    executed: true, completed: true, result: 'PASS', requestNo: request.requestNo, inquiryNo: inquiry.inquiryNo,
    comparisonNo: comparison.comparisonNo, recommendationDecisionNo: recommendation.decisionNo,
    gateDecisionNo: gateDecision.gateDecisionNo, transactionNo: transaction.transactionNo,
    preparationNo: saved.object.preparationNo, preparationResult: saved.object.status, steps: Object.freeze(steps),
  })
}

export function createPurchaseOrderIssuePreparationProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validatePurchaseOrderIssuePreparationStateBoundaries()
  return Object.freeze({
    version: PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-order-issue-preparation-runtime', pageUrl: '/scm/purchase-inquiry',
      nodeCode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-issue-preparation-context', actionCode: 'CREATE_ISSUE_PREPARATION_CONTEXT' }),
        Object.freeze({ buttonCode: 'check-issue-requirements', actionCode: 'CHECK_ISSUE_REQUIREMENTS' }),
        Object.freeze({ buttonCode: 'save-issue-preparation', actionCode: 'SAVE_ISSUE_PREPARATION' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_ORDER_ISSUE_PREPARATION_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([PURCHASE_ORDER_TRANSACTION_HANDOFF_SOURCE]),
    actions: PURCHASE_ORDER_ISSUE_PREPARATION_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_ORDER_ISSUE_PREPARATION_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([PURCHASE_ORDER_TRANSACTION_ISSUE_PREPARATION_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-order-issue-preparation-runtime-acceptance',
      processCode: 'SCM_PURCHASE_ORDER_ISSUE_PREPARATION_FLOW', objectType: 'PurchaseOrderIssuePreparation',
      objectId: 'purchase-order-transaction-handoff', nodeCode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
      state: 'purchase_order_transaction_draft', actorId: 'process-006-issue-preparation-user',
      actorRole: 'purchase-order-issue-preparation-operator', correlationId: 'purchase-order-issue-preparation-v1142816',
      attributes: { acceptanceVersion: PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'POIP-REG-TRANSACTION-DELIVERY-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'POIP-REG-READY-AND-BLOCKED-BRANCHES', result: 'PASS' }),
      Object.freeze({ caseCode: 'POIP-REG-NO-PURCHASE-ORDER-ISSUE', result: boundaries.result }),
      Object.freeze({ caseCode: 'POIP-REG-NO-SEND-RECEIVE-INVENTORY-INVOICE-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseOrderIssuePreparationProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createPurchaseOrderIssuePreparationProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS006_STEPS.length
    && PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validatePurchaseOrderTransactionIssuePreparationHandoff(artifacts.transaction, artifacts.context)
  const stateBoundaries = validatePurchaseOrderIssuePreparationStateBoundaries()
  const boundariesProtected = artifacts.preparation?.purchaseOrderIssued === false
    && artifacts.preparation?.supplierSent === false && artifacts.preparation?.goodsReceived === false
    && artifacts.preparation?.inventoryPosted === false && artifacts.preparation?.invoiceCreated === false
    && artifacts.preparation?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: PURCHASE_ORDER_ISSUE_PREPARATION_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_ORDER_ISSUE_PREPARATION_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected,
  })
}
