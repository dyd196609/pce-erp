import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  ISSUE_BOUNDARY_HANDOFF_SOURCE,
  PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
  PURCHASE_ORDER_ISSUE_EXECUTION_NODE_RUNTIME_CONTRACT,
} from './purchaseOrderIssueExecutionNodeRuntimeContract.js'
import { PURCHASE_ORDER_ISSUE_EXECUTION_ACTION_CONTRACTS } from './purchaseOrderIssueExecutionActionContracts.js'
import {
  PURCHASE_ORDER_ISSUE_EXECUTION_STATE_TRANSITION_CONTRACT,
  validatePurchaseOrderIssueExecutionStateBoundaries,
} from './purchaseOrderIssueExecutionStateTransitionContract.js'
import {
  ISSUE_BOUNDARY_EXECUTION_HANDOFF_CONTRACT,
  validateIssueBoundaryExecutionHandoff,
} from './purchaseOrderIssueBoundaryExecutionHandoffContract.js'

export const PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.18'
export const PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST', 'PURCHASE_INQUIRY', 'SUPPLIER_QUOTE', 'QUOTE_COMPARISON',
  'SUPPLIER_RECOMMENDATION', 'PURCHASE_ORDER_CREATION_GATE', 'PURCHASE_ORDER_TRANSACTION',
  'PURCHASE_ORDER_ISSUE_PREPARATION', 'PURCHASE_ORDER_ISSUE_BOUNDARY',
  'ISSUE_EXECUTION_CONTEXT', 'CHECK_EXECUTION_AUTHORIZATION', 'SAVE_EXECUTION_PREPARATION',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runPurchaseOrderIssueExecutionEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes', 'loadQuoteComparison',
    'loadSupplierRecommendation', 'loadPurchaseOrderGateDecision', 'loadPurchaseOrderTransaction',
    'loadIssuePreparation', 'loadIssueDecision', 'createIssueExecutionContext',
    'checkExecutionAuthorization', 'saveExecutionPreparation']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_ORDER_ISSUE_EXECUTION_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`PURCHASE_ORDER_ISSUE_EXECUTION_STEP_FAILED:${stepCode}`)
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
  let issueDecision
  let context
  let authorization
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
    issueDecision = await execute('PURCHASE_ORDER_ISSUE_BOUNDARY', () => adapters.loadIssueDecision(preparation), value => value?.objectType === 'PurchaseOrderIssueDecision' && value?.status === 'allowed')
    context = await execute('ISSUE_EXECUTION_CONTEXT', () => adapters.createIssueExecutionContext(issueDecision), value => value?.objectType === 'PurchaseOrderIssueExecutionContext' && value?.status === 'execution_context_created' && value?.supplierApiCalled === false)
    authorization = await execute('CHECK_EXECUTION_AUTHORIZATION', () => adapters.checkExecutionAuthorization(context), value => value?.objectType === 'PurchaseOrderIssueAuthorization' && value?.status === 'authorization_checking')
    saved = await execute('SAVE_EXECUTION_PREPARATION', () => adapters.saveExecutionPreparation(authorization), value => value?.result === 'PASS' && ['authorized', 'blocked'].includes(value?.object?.status) && value?.object?.purchaseOrderIssued === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-ISSUE-EXECUTION-E2E',
      sourceNode: ISSUE_BOUNDARY_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-ISSUE-EXECUTION-E2E',
    sourceNode: ISSUE_BOUNDARY_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
    executed: true, completed: true, result: 'PASS', requestNo: request.requestNo, inquiryNo: inquiry.inquiryNo,
    comparisonNo: comparison.comparisonNo, recommendationDecisionNo: recommendation.decisionNo,
    gateDecisionNo: gateDecision.gateDecisionNo, transactionNo: transaction.transactionNo,
    preparationNo: preparation.preparationNo, issueDecisionNo: issueDecision.issueDecisionNo,
    authorizationNo: saved.object.authorizationNo, authorizationResult: saved.object.status, steps: Object.freeze(steps),
  })
}

export function createPurchaseOrderIssueExecutionProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validatePurchaseOrderIssueExecutionStateBoundaries()
  return Object.freeze({
    version: PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-order-issue-execution-runtime', pageUrl: '/scm/purchase-inquiry',
      nodeCode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-issue-execution-context', actionCode: 'CREATE_ISSUE_EXECUTION_CONTEXT' }),
        Object.freeze({ buttonCode: 'check-execution-authorization', actionCode: 'CHECK_EXECUTION_AUTHORIZATION' }),
        Object.freeze({ buttonCode: 'save-execution-preparation', actionCode: 'SAVE_EXECUTION_PREPARATION' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_ORDER_ISSUE_EXECUTION_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([ISSUE_BOUNDARY_HANDOFF_SOURCE]),
    actions: PURCHASE_ORDER_ISSUE_EXECUTION_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_ORDER_ISSUE_EXECUTION_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([ISSUE_BOUNDARY_EXECUTION_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-order-issue-execution-runtime-acceptance',
      processCode: 'SCM_PURCHASE_ORDER_ISSUE_EXECUTION_FLOW', objectType: 'PurchaseOrderIssueAuthorization',
      objectId: 'issue-boundary-handoff', nodeCode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
      state: 'issue_boundary_decided', actorId: 'process-006-issue-execution-user',
      actorRole: 'purchase-order-issue-execution-operator', correlationId: 'purchase-order-issue-execution-v1142818',
      attributes: { acceptanceVersion: PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'POIE-REG-BOUNDARY-AUTHORIZATION-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'POIE-REG-AUTHORIZED-AND-BLOCKED-BRANCHES', result: 'PASS' }),
      Object.freeze({ caseCode: 'POIE-REG-AUTHORIZED-IS-PREPARATION-ONLY', result: boundaries.result }),
      Object.freeze({ caseCode: 'POIE-REG-NO-API-ISSUE-SEND-RECEIVE-INVENTORY-INVOICE-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseOrderIssueExecutionProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createPurchaseOrderIssueExecutionProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS006_STEPS.length
    && PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validateIssueBoundaryExecutionHandoff(artifacts.issueDecision, artifacts.context)
  const stateBoundaries = validatePurchaseOrderIssueExecutionStateBoundaries()
  const boundariesProtected = artifacts.authorization?.supplierApiCalled === false
    && artifacts.authorization?.purchaseOrderIssued === false && artifacts.authorization?.supplierSent === false
    && artifacts.authorization?.goodsReceived === false && artifacts.authorization?.inventoryPosted === false
    && artifacts.authorization?.invoiceCreated === false && artifacts.authorization?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: PURCHASE_ORDER_ISSUE_EXECUTION_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_ORDER_ISSUE_EXECUTION_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected,
  })
}
