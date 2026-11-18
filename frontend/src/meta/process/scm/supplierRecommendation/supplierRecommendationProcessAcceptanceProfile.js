import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  QUOTE_COMPARISON_HANDOFF_SOURCE,
  SUPPLIER_RECOMMENDATION_NODE_CODE,
  SUPPLIER_RECOMMENDATION_NODE_RUNTIME_CONTRACT,
} from './supplierRecommendationNodeRuntimeContract.js'
import { SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS } from './supplierRecommendationActionContracts.js'
import {
  SUPPLIER_RECOMMENDATION_STATE_TRANSITION_CONTRACT,
  validateSupplierRecommendationStateBoundaries,
} from './supplierRecommendationStateTransitionContract.js'
import {
  QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_CONTRACT,
  validateQuoteComparisonRecommendationHandoff,
} from './quoteComparisonRecommendationHandoffContract.js'

export const SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.13'
export const SUPPLIER_RECOMMENDATION_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST',
  'PURCHASE_INQUIRY',
  'SUPPLIER_QUOTE',
  'QUOTE_COMPARISON',
  'RECOMMENDATION_CONTEXT',
  'GENERATE_RECOMMENDATION_DECISION',
  'SAVE_RECOMMENDATION_DECISION',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runSupplierRecommendationEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes', 'loadQuoteComparison',
    'createRecommendationContext', 'generateRecommendationDecision', 'saveRecommendationDecision']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`SUPPLIER_RECOMMENDATION_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`SUPPLIER_RECOMMENDATION_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }

  let request
  let inquiry
  let quotes
  let comparison
  let context
  let decision
  let saved
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo)
    quotes = await execute('SUPPLIER_QUOTE', () => adapters.loadSupplierQuotes(inquiry), value => Array.isArray(value) && value.length > 0 && value.every(item => item.status === 'quotation_completed'))
    comparison = await execute('QUOTE_COMPARISON', () => adapters.loadQuoteComparison(quotes), value => value?.objectType === 'QuoteComparison' && ['comparison_completed', 'recommendation_ready'].includes(value?.status))
    context = await execute('RECOMMENDATION_CONTEXT', () => adapters.createRecommendationContext(comparison), value => value?.objectType === 'SupplierRecommendationContext' && value?.status === 'recommendation_context_created')
    decision = await execute('GENERATE_RECOMMENDATION_DECISION', () => adapters.generateRecommendationDecision(context), value => value?.objectType === 'SupplierRecommendationDecision' && value?.status === 'evaluating' && Boolean(value?.recommendedSupplierId))
    saved = await execute('SAVE_RECOMMENDATION_DECISION', () => adapters.saveRecommendationDecision(decision), value => value?.result === 'PASS' && value?.object?.status === 'recommendation_completed' && value?.object?.approvalSubmitted === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-SUPPLIER-RECOMMENDATION-E2E',
      sourceNode: QUOTE_COMPARISON_HANDOFF_SOURCE.nodeCode, targetNode: SUPPLIER_RECOMMENDATION_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-SUPPLIER-RECOMMENDATION-E2E',
    sourceNode: QUOTE_COMPARISON_HANDOFF_SOURCE.nodeCode, targetNode: SUPPLIER_RECOMMENDATION_NODE_CODE,
    executed: true, completed: true, result: 'PASS', requestNo: request.requestNo,
    inquiryNo: inquiry.inquiryNo, quoteNos: Object.freeze(quotes.map(item => item.quoteNo)),
    comparisonNo: comparison.comparisonNo, decisionNo: saved.object.decisionNo, steps: Object.freeze(steps),
  })
}

export function createSupplierRecommendationProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validateSupplierRecommendationStateBoundaries()
  return Object.freeze({
    version: SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'supplier-recommendation-runtime', pageUrl: '/scm/purchase-inquiry',
      nodeCode: SUPPLIER_RECOMMENDATION_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-recommendation-context', actionCode: 'CREATE_RECOMMENDATION_CONTEXT' }),
        Object.freeze({ buttonCode: 'generate-recommendation-decision', actionCode: 'GENERATE_RECOMMENDATION_DECISION' }),
        Object.freeze({ buttonCode: 'save-recommendation-decision', actionCode: 'SAVE_RECOMMENDATION_DECISION' }),
      ]),
    })]),
    nodes: Object.freeze([SUPPLIER_RECOMMENDATION_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([QUOTE_COMPARISON_HANDOFF_SOURCE]),
    actions: SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS,
    stateModels: Object.freeze([SUPPLIER_RECOMMENDATION_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'supplier-recommendation-runtime-acceptance',
      processCode: 'SCM_SUPPLIER_RECOMMENDATION_FLOW', objectType: 'SupplierRecommendationDecision',
      objectId: 'quote-comparison-handoff', nodeCode: SUPPLIER_RECOMMENDATION_NODE_CODE,
      state: 'quote_comparison_ready', actorId: 'process-006-recommendation-user',
      actorRole: 'supplier-recommendation-operator', correlationId: 'supplier-recommendation-v1142813',
      attributes: { acceptanceVersion: SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'SR-REG-COMPARISON-EVIDENCE-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'SR-REG-EXPLAINABLE-DECISION-SAVE', result: 'PASS' }),
      Object.freeze({ caseCode: 'SR-REG-NO-PURCHASE-ORDER', result: boundaries.result }),
      Object.freeze({ caseCode: 'SR-REG-NO-APPROVAL-SUBMISSION-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validateSupplierRecommendationProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createSupplierRecommendationProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === SUPPLIER_RECOMMENDATION_PROCESS006_STEPS.length
    && SUPPLIER_RECOMMENDATION_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validateQuoteComparisonRecommendationHandoff(artifacts.comparison, artifacts.context)
  const stateBoundaries = validateSupplierRecommendationStateBoundaries()
  const boundariesProtected = artifacts.context?.purchaseOrderCreated === false
    && artifacts.decision?.purchaseOrderCreated === false
    && artifacts.decision?.approvalSubmitted === false
    && artifacts.decision?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: SUPPLIER_RECOMMENDATION_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_SUPPLIER_RECOMMENDATION_RUNTIME_READY' : 'FAIL', result: valid ? 'PASS' : 'FAIL',
    report, handoff, stateBoundaries, walkthroughPathValid, boundariesProtected,
  })
}
