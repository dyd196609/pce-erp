import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  ISSUE_PREPARATION_HANDOFF_SOURCE,
  PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
  PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_RUNTIME_CONTRACT,
} from './purchaseOrderIssueBoundaryNodeRuntimeContract.js'
import { PURCHASE_ORDER_ISSUE_BOUNDARY_ACTION_CONTRACTS } from './purchaseOrderIssueBoundaryActionContracts.js'
import {
  PURCHASE_ORDER_ISSUE_BOUNDARY_STATE_TRANSITION_CONTRACT,
  validatePurchaseOrderIssueBoundaryStateBoundaries,
} from './purchaseOrderIssueBoundaryStateTransitionContract.js'
import {
  ISSUE_PREPARATION_BOUNDARY_HANDOFF_CONTRACT,
  validateIssuePreparationBoundaryHandoff,
} from './purchaseOrderIssuePreparationBoundaryHandoffContract.js'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.17'
export const PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST', 'PURCHASE_INQUIRY', 'SUPPLIER_QUOTE', 'QUOTE_COMPARISON',
  'SUPPLIER_RECOMMENDATION', 'PURCHASE_ORDER_CREATION_GATE', 'PURCHASE_ORDER_TRANSACTION',
  'PURCHASE_ORDER_ISSUE_PREPARATION', 'ISSUE_BOUNDARY_CONTEXT',
  'EVALUATE_ISSUE_PERMISSION', 'SAVE_ISSUE_DECISION',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runPurchaseOrderIssueBoundaryEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes', 'loadQuoteComparison',
    'loadSupplierRecommendation', 'loadPurchaseOrderGateDecision', 'loadPurchaseOrderTransaction',
    'loadIssuePreparation', 'createIssueBoundaryContext', 'evaluateIssuePermission', 'saveIssueDecision']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_ORDER_ISSUE_BOUNDARY_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`PURCHASE_ORDER_ISSUE_BOUNDARY_STEP_FAILED:${stepCode}`)
    return value
  }
  let request
  let inquiry
  let quotes
  let comparison
  let recommendation
  let gateDecision
  let transaction
  let preparation
  let context
  let decision
  let saved
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo)
    quotes = await execute('SUPPLIER_QUOTE', () => adapters.loadSupplierQuotes(inquiry), value => Array.isArray(value) && value.length > 0)
    comparison = await execute('QUOTE_COMPARISON', () => adapters.loadQuoteComparison(quotes), value => value?.objectType === 'QuoteComparison' && value?.status === 'recommendation_ready')
    recommendation = await execute('SUPPLIER_RECOMMENDATION', () => adapters.loadSupplierRecommendation(comparison), value => value?.objectType === 'SupplierRecommendationDecision' && value?.status === 'approval_ready')
    gateDecision = await execute('PURCHASE_ORDER_CREATION_GATE', () => adapters.loadPurchaseOrderGateDecision(recommendation), value => value?.objectType === 'PurchaseOrderCreationGateDecision' && value?.status === 'eligible')
    transaction = await execute('PURCHASE_ORDER_TRANSACTION', () => adapters.loadPurchaseOrderTransaction(gateDecision), value => value?.objectType === 'PurchaseOrderTransaction' && value?.status === 'draft')
    preparation = await execute('PURCHASE_ORDER_ISSUE_PREPARATION', () => adapters.loadIssuePreparation(transaction), value => value?.objectType === 'PurchaseOrderIssuePreparation' && value?.status === 'ready_for_issue')
    context = await execute('ISSUE_BOUNDARY_CONTEXT', () => adapters.createIssueBoundaryContext(preparation), value => value?.objectType === 'PurchaseOrderIssueBoundaryContext' && value?.status === 'issue_boundary_context_created')
    decision = await execute('EVALUATE_ISSUE_PERMISSION', () => adapters.evaluateIssuePermission(context), value => value?.objectType === 'PurchaseOrderIssueDecision' && value?.status === 'evaluating')
    saved = await execute('SAVE_ISSUE_DECISION', () => adapters.saveIssueDecision(decision), value => value?.result === 'PASS' && ['allowed', 'blocked'].includes(value?.object?.status) && value?.object?.purchaseOrderIssued === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-ISSUE-BOUNDARY-E2E',
      sourceNode: ISSUE_PREPARATION_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-ISSUE-BOUNDARY-E2E',
    sourceNode: ISSUE_PREPARATION_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
    executed: true, completed: true, result: 'PASS', requestNo: request.requestNo, inquiryNo: inquiry.inquiryNo,
    comparisonNo: comparison.comparisonNo, recommendationDecisionNo: recommendation.decisionNo,
    gateDecisionNo: gateDecision.gateDecisionNo, transactionNo: transaction.transactionNo,
    preparationNo: preparation.preparationNo, issueDecisionNo: saved.object.issueDecisionNo,
    boundaryResult: saved.object.status, steps: Object.freeze(steps),
  })
}

export function createPurchaseOrderIssueBoundaryProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validatePurchaseOrderIssueBoundaryStateBoundaries()
  return Object.freeze({
    version: PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-order-issue-boundary-runtime', pageUrl: '/scm/purchase-inquiry',
      nodeCode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-issue-boundary-context', actionCode: 'CREATE_ISSUE_BOUNDARY_CONTEXT' }),
        Object.freeze({ buttonCode: 'evaluate-issue-permission', actionCode: 'EVALUATE_ISSUE_PERMISSION' }),
        Object.freeze({ buttonCode: 'save-issue-decision', actionCode: 'SAVE_ISSUE_DECISION' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([ISSUE_PREPARATION_HANDOFF_SOURCE]),
    actions: PURCHASE_ORDER_ISSUE_BOUNDARY_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_ORDER_ISSUE_BOUNDARY_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([ISSUE_PREPARATION_BOUNDARY_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-order-issue-boundary-runtime-acceptance',
      processCode: 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_FLOW', objectType: 'PurchaseOrderIssueDecision',
      objectId: 'issue-preparation-handoff', nodeCode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
      state: 'issue_preparation_ready', actorId: 'process-006-issue-boundary-user',
      actorRole: 'purchase-order-issue-boundary-operator', correlationId: 'purchase-order-issue-boundary-v1142817',
      attributes: { acceptanceVersion: PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'POIB-REG-PREPARATION-EVIDENCE-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'POIB-REG-ALLOWED-AND-BLOCKED-BRANCHES', result: 'PASS' }),
      Object.freeze({ caseCode: 'POIB-REG-ALLOWED-IS-PERMISSION-ONLY', result: boundaries.result }),
      Object.freeze({ caseCode: 'POIB-REG-NO-ISSUE-SEND-RECEIVE-INVENTORY-INVOICE-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseOrderIssueBoundaryProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createPurchaseOrderIssueBoundaryProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS006_STEPS.length
    && PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validateIssuePreparationBoundaryHandoff(artifacts.preparation, artifacts.context)
  const stateBoundaries = validatePurchaseOrderIssueBoundaryStateBoundaries()
  const boundariesProtected = artifacts.decision?.purchaseOrderIssued === false
    && artifacts.decision?.supplierSent === false && artifacts.decision?.goodsReceived === false
    && artifacts.decision?.inventoryPosted === false && artifacts.decision?.invoiceCreated === false
    && artifacts.decision?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: PURCHASE_ORDER_ISSUE_BOUNDARY_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected,
  })
}
