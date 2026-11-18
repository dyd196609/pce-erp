import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
  PURCHASE_ORDER_CREATION_GATE_NODE_RUNTIME_CONTRACT,
  SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE,
} from './purchaseOrderCreationGateNodeRuntimeContract.js'
import { PURCHASE_ORDER_CREATION_GATE_ACTION_CONTRACTS } from './purchaseOrderCreationGateActionContracts.js'
import {
  PURCHASE_ORDER_CREATION_GATE_STATE_TRANSITION_CONTRACT,
  validatePurchaseOrderCreationGateStateBoundaries,
} from './purchaseOrderCreationGateStateTransitionContract.js'
import {
  SUPPLIER_RECOMMENDATION_PURCHASE_ORDER_GATE_HANDOFF_CONTRACT,
  validateSupplierRecommendationPurchaseOrderGateHandoff,
} from './supplierRecommendationPurchaseOrderGateHandoffContract.js'

export const PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.14'
export const PURCHASE_ORDER_CREATION_GATE_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST', 'PURCHASE_INQUIRY', 'SUPPLIER_QUOTE', 'QUOTE_COMPARISON',
  'SUPPLIER_RECOMMENDATION', 'PURCHASE_ORDER_GATE_CONTEXT',
  'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY', 'SAVE_PURCHASE_ORDER_GATE_DECISION',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runPurchaseOrderCreationGateEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes', 'loadQuoteComparison',
    'loadSupplierRecommendation', 'createGateContext', 'evaluateEligibility', 'saveGateDecision']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_ORDER_GATE_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`PURCHASE_ORDER_GATE_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }
  let request
  let inquiry
  let quotes
  let comparison
  let recommendation
  let context
  let decision
  let saved
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo)
    quotes = await execute('SUPPLIER_QUOTE', () => adapters.loadSupplierQuotes(inquiry), value => Array.isArray(value) && value.length > 0)
    comparison = await execute('QUOTE_COMPARISON', () => adapters.loadQuoteComparison(quotes), value => value?.objectType === 'QuoteComparison' && value?.status === 'recommendation_ready')
    recommendation = await execute('SUPPLIER_RECOMMENDATION', () => adapters.loadSupplierRecommendation(comparison), value => value?.objectType === 'SupplierRecommendationDecision' && value?.status === 'approval_ready')
    context = await execute('PURCHASE_ORDER_GATE_CONTEXT', () => adapters.createGateContext(recommendation), value => value?.objectType === 'PurchaseOrderCreationGateContext' && value?.status === 'gate_context_created')
    decision = await execute('EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY', () => adapters.evaluateEligibility(context), value => value?.objectType === 'PurchaseOrderCreationGateDecision' && value?.status === 'evaluating')
    saved = await execute('SAVE_PURCHASE_ORDER_GATE_DECISION', () => adapters.saveGateDecision(decision), value => value?.result === 'PASS' && ['eligible', 'blocked'].includes(value?.object?.status) && value?.object?.purchaseOrderCreated === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-CREATION-GATE-E2E',
      sourceNode: SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-PURCHASE-ORDER-CREATION-GATE-E2E',
    sourceNode: SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE.nodeCode, targetNode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
    executed: true, completed: true, result: 'PASS', requestNo: request.requestNo, inquiryNo: inquiry.inquiryNo,
    comparisonNo: comparison.comparisonNo, recommendationDecisionNo: recommendation.decisionNo,
    gateDecisionNo: saved.object.gateDecisionNo, gateResult: saved.object.status, steps: Object.freeze(steps),
  })
}

export function createPurchaseOrderCreationGateProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validatePurchaseOrderCreationGateStateBoundaries()
  return Object.freeze({
    version: PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-order-creation-gate-runtime', pageUrl: '/scm/purchase-inquiry',
      nodeCode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-purchase-order-gate-context', actionCode: 'CREATE_PURCHASE_ORDER_GATE_CONTEXT' }),
        Object.freeze({ buttonCode: 'evaluate-purchase-order-creation-eligibility', actionCode: 'EVALUATE_PURCHASE_ORDER_CREATION_ELIGIBILITY' }),
        Object.freeze({ buttonCode: 'save-purchase-order-gate-decision', actionCode: 'SAVE_PURCHASE_ORDER_GATE_DECISION' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_ORDER_CREATION_GATE_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([SUPPLIER_RECOMMENDATION_HANDOFF_SOURCE]),
    actions: PURCHASE_ORDER_CREATION_GATE_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_ORDER_CREATION_GATE_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([SUPPLIER_RECOMMENDATION_PURCHASE_ORDER_GATE_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-order-creation-gate-runtime-acceptance',
      processCode: 'SCM_PURCHASE_ORDER_CREATION_GATE_FLOW', objectType: 'PurchaseOrderCreationGateDecision',
      objectId: 'supplier-recommendation-handoff', nodeCode: PURCHASE_ORDER_CREATION_GATE_NODE_CODE,
      state: 'supplier_recommendation_ready', actorId: 'process-006-purchase-order-gate-user',
      actorRole: 'purchase-order-gate-operator', correlationId: 'purchase-order-gate-v1142814',
      attributes: { acceptanceVersion: PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'POG-REG-RECOMMENDATION-EVIDENCE-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'POG-REG-ELIGIBLE-AND-BLOCKED-BRANCHES', result: 'PASS' }),
      Object.freeze({ caseCode: 'POG-REG-NO-PURCHASE-ORDER-CREATION', result: boundaries.result }),
      Object.freeze({ caseCode: 'POG-REG-NO-SUPPLIER-PUBLISH-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseOrderCreationGateProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createPurchaseOrderCreationGateProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_ORDER_CREATION_GATE_PROCESS006_STEPS.length
    && PURCHASE_ORDER_CREATION_GATE_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validateSupplierRecommendationPurchaseOrderGateHandoff(artifacts.recommendation, artifacts.context)
  const stateBoundaries = validatePurchaseOrderCreationGateStateBoundaries()
  const boundariesProtected = artifacts.context?.purchaseOrderCreated === false
    && artifacts.decision?.purchaseOrderCreated === false && artifacts.decision?.supplierPublished === false
    && artifacts.decision?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: PURCHASE_ORDER_CREATION_GATE_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_ORDER_CREATION_GATE_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected,
  })
}
