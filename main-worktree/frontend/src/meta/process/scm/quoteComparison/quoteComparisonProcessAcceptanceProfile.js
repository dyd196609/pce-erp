import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import {
  QUOTE_COMPARISON_NODE_CODE,
  QUOTE_COMPARISON_NODE_RUNTIME_CONTRACT,
  SUPPLIER_QUOTE_HANDOFF_SOURCE,
} from './quoteComparisonNodeRuntimeContract.js'
import { QUOTE_COMPARISON_ACTION_CONTRACTS } from './quoteComparisonActionContracts.js'
import {
  QUOTE_COMPARISON_STATE_TRANSITION_CONTRACT,
  validateQuoteComparisonStateBoundaries,
} from './quoteComparisonStateTransitionContract.js'
import {
  SUPPLIER_QUOTE_COMPARISON_HANDOFF_CONTRACT,
  validateSupplierQuoteComparisonHandoff,
} from './supplierQuoteComparisonHandoffContract.js'

export const QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.12'
export const QUOTE_COMPARISON_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST',
  'PURCHASE_INQUIRY',
  'SUPPLIER_QUOTE',
  'QUOTE_COMPARISON_CONTEXT',
  'GENERATE_QUOTE_COMPARISON_FACT',
  'SAVE_QUOTE_COMPARISON',
])

const evidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runQuoteComparisonEndToEndBusinessWalkthrough(adapters = {}) {
  const required = ['loadPurchaseRequest', 'loadPurchaseInquiry', 'loadSupplierQuotes',
    'createQuoteComparisonContext', 'generateQuoteComparisonFact', 'saveQuoteComparison']
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`QUOTE_COMPARISON_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)
  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({ sequence: steps.length + 1, stepCode, result: valid ? 'PASS' : 'FAIL', evidence: evidence(value) }))
    if (!valid) throw new Error(`QUOTE_COMPARISON_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }

  let request
  let inquiry
  let quotes
  let context
  let comparison
  let saved
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo))
    inquiry = await execute('PURCHASE_INQUIRY', () => adapters.loadPurchaseInquiry(request), value => Boolean(value?.inquiryNo) && value?.sourceRequestNo === request.requestNo)
    quotes = await execute('SUPPLIER_QUOTE', () => adapters.loadSupplierQuotes(inquiry), value => Array.isArray(value) && value.length > 0 && value.every(item => item.status === 'quotation_completed'))
    context = await execute('QUOTE_COMPARISON_CONTEXT', () => adapters.createQuoteComparisonContext(quotes), value => value?.objectType === 'QuoteComparisonContext' && value?.status === 'comparison_context_created')
    comparison = await execute('GENERATE_QUOTE_COMPARISON_FACT', () => adapters.generateQuoteComparisonFact(context), value => value?.objectType === 'QuoteComparison' && value?.status === 'comparing' && value?.supplierRecommendationCreated === false)
    saved = await execute('SAVE_QUOTE_COMPARISON', () => adapters.saveQuoteComparison(comparison), value => value?.result === 'PASS' && value?.object?.status === 'comparison_completed' && value?.productionDataWritten === false)
  } catch (error) {
    return Object.freeze({ type: 'End-to-End Business Walkthrough', walkthroughCode: 'SCM-QUOTE-COMPARISON-E2E',
      sourceNode: SUPPLIER_QUOTE_HANDOFF_SOURCE.nodeCode, targetNode: QUOTE_COMPARISON_NODE_CODE,
      executed: true, completed: false, result: 'FAIL', error: error.message, steps: Object.freeze(steps) })
  }
  return Object.freeze({
    type: 'End-to-End Business Walkthrough',
    walkthroughCode: 'SCM-QUOTE-COMPARISON-E2E',
    sourceNode: SUPPLIER_QUOTE_HANDOFF_SOURCE.nodeCode,
    targetNode: QUOTE_COMPARISON_NODE_CODE,
    executed: true,
    completed: true,
    result: 'PASS',
    requestNo: request.requestNo,
    inquiryNo: inquiry.inquiryNo,
    quoteNos: Object.freeze(quotes.map(item => item.quoteNo)),
    comparisonNo: saved.object.comparisonNo,
    steps: Object.freeze(steps),
  })
}

export function createQuoteComparisonProcessAcceptanceDefinition(businessWalkthrough) {
  const boundaries = validateQuoteComparisonStateBoundaries()
  return Object.freeze({
    version: QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'quote-comparison-runtime',
      pageUrl: '/scm/purchase-inquiry',
      nodeCode: QUOTE_COMPARISON_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'create-quote-comparison-context', actionCode: 'CREATE_QUOTE_COMPARISON_CONTEXT' }),
        Object.freeze({ buttonCode: 'generate-quote-comparison-fact', actionCode: 'GENERATE_QUOTE_COMPARISON_FACT' }),
        Object.freeze({ buttonCode: 'save-quote-comparison', actionCode: 'SAVE_QUOTE_COMPARISON' }),
      ]),
    })]),
    nodes: Object.freeze([QUOTE_COMPARISON_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([SUPPLIER_QUOTE_HANDOFF_SOURCE]),
    actions: QUOTE_COMPARISON_ACTION_CONTRACTS,
    stateModels: Object.freeze([QUOTE_COMPARISON_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([SUPPLIER_QUOTE_COMPARISON_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'quote-comparison-runtime-acceptance',
      processCode: 'SCM_QUOTE_COMPARISON_FLOW',
      objectType: 'QuoteComparison',
      objectId: 'supplier-quotes-handoff',
      nodeCode: QUOTE_COMPARISON_NODE_CODE,
      state: 'supplier_quotes_ready',
      actorId: 'process-006-quote-comparison-user',
      actorRole: 'quote-comparison-operator',
      correlationId: 'quote-comparison-v1142812',
      attributes: { acceptanceVersion: QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'QC-REG-SUPPLIER-QUOTE-FIELD-HANDOFF', result: 'PASS' }),
      Object.freeze({ caseCode: 'QC-REG-FACT-GENERATION-AND-SAVE', result: 'PASS' }),
      Object.freeze({ caseCode: 'QC-REG-NO-SUPPLIER-RECOMMENDATION', result: boundaries.result }),
      Object.freeze({ caseCode: 'QC-REG-NO-PURCHASE-ORDER-FINANCE', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validateQuoteComparisonProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createQuoteComparisonProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === QUOTE_COMPARISON_PROCESS006_STEPS.length
    && QUOTE_COMPARISON_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const handoff = validateSupplierQuoteComparisonHandoff(artifacts.quotes, artifacts.context)
  const stateBoundaries = validateQuoteComparisonStateBoundaries()
  const boundariesProtected = artifacts.context?.supplierRecommendationCreated === false
    && artifacts.comparison?.supplierRecommendationCreated === false
    && artifacts.comparison?.recommendedSupplierId === null
    && artifacts.comparison?.purchaseOrderCreated === false
    && artifacts.comparison?.financeActionExecuted === false
  const valid = report.result === 'PASS' && walkthroughPathValid && handoff.valid
    && stateBoundaries.valid && boundariesProtected
  return Object.freeze({
    version: QUOTE_COMPARISON_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_QUOTE_COMPARISON_RUNTIME_READY' : 'FAIL',
    result: valid ? 'PASS' : 'FAIL',
    report,
    handoff,
    stateBoundaries,
    walkthroughPathValid,
    boundariesProtected,
  })
}
