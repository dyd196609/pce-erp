import { validateQuoteComparisonNodeContractV1142810 } from './quoteComparisonNodeContractV1142810.js'
import { validateQuoteComparisonDomain } from './quoteComparisonDomainModelV1142810.js'
import { QUOTE_COMPARISON_STATES_V1142810, QUOTE_COMPARISON_BOUNDARY } from './quoteComparisonStateContractV1142810.js'
import { QUOTE_COMPARISON_ACTION_CONTRACTS_V1142810, QUOTE_COMPARISON_FORBIDDEN_ACTIONS } from './quoteComparisonActionContractsV1142810.js'
import { validateQuoteComparisonProviderContractV1142810 } from './quoteComparisonProviderContractV1142810.js'
import { validateQuoteComparisonPageContractV1142810 } from './quoteComparisonPageContractV1142810.js'
import { createQuoteComparisonProvider } from '../../../providers/quoteComparisonProviderV1142810.js'
import { executeCreateQuoteComparisonContext, executeGenerateQuoteComparison,
  executeSaveQuoteComparison } from '../../../runtime/quoteComparisonActionRuntimeV1142810.js'

export const QUOTE_COMPARISON_ACCEPTANCE_VERSION = 'V1.14.2.8.18.10'

export function runQuoteComparisonBusinessWalkthrough({ inquiryNo, sourceProvider, store, asOf = '2026-08-05' }) {
  const provider = createQuoteComparisonProvider({ sourceProvider, store })
  const steps = []
  const record = (stepCode, result, facts = {}) => steps.push(Object.freeze({
    sequence: steps.length + 1, stepCode, result, facts: Object.freeze({ ...facts }),
  }))
  const loaded = provider.load({ inquiryNo })
  record('SUPPLIER_QUOTE', loaded.recordCount ? 'PASS' : 'FAIL', { inquiryNo, quoteCount: loaded.current?.quoteCount })
  if (!loaded.recordCount) return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })
  const created = executeCreateQuoteComparisonContext(loaded.current.sourceFacts, store)
  record('ENTER_QUOTE_COMPARISON', created.result, { comparisonPreparationNo: created.context?.comparisonPreparationNo })
  if (created.result === 'FAIL') return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })
  const generated = executeGenerateQuoteComparison(created.context, store, asOf)
  record('GENERATE_QUOTE_COMPARISON', generated.result, { comparisonCount: generated.comparisons?.length })
  if (generated.result === 'FAIL') return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })
  const saved = executeSaveQuoteComparison(generated.context, store)
  record('SAVE_QUOTE_COMPARISON', saved.result, { status: saved.context?.comparisonStatus })
  return Object.freeze({ result: saved.result, steps: Object.freeze(steps), context: saved.context,
    comparisons: saved.comparisons, nextPreparation: saved.nextPreparation,
    supplierRecommendationCreated: false, purchaseOrderCreated: false, financeCreated: false })
}

export function validateQuoteComparisonAcceptanceV1142810({ walkthrough, sourceProvider, store }) {
  const providerFacts = createQuoteComparisonProvider({ sourceProvider, store }).load()
  const node = validateQuoteComparisonNodeContractV1142810()
  const domain = validateQuoteComparisonDomain(walkthrough.context, walkthrough.comparisons)
  const state = QUOTE_COMPARISON_STATES_V1142810.join('>')
    === 'supplier_quote_completed>comparison_preparing>comparison_ready'
    && walkthrough.context?.comparisonStatus === 'comparison_ready'
  const action = Object.keys(QUOTE_COMPARISON_ACTION_CONTRACTS_V1142810).length === 3
    && QUOTE_COMPARISON_FORBIDDEN_ACTIONS.includes('CREATE_SUPPLIER_RECOMMENDATION')
    && QUOTE_COMPARISON_FORBIDDEN_ACTIONS.includes('CREATE_PURCHASE_ORDER')
  const handoff = providerFacts.factSource === 'SupplierQuoteProvider'
    && providerFacts.records.every(item => item.sourceFacts.inquiryNo === item.inquiryNo
      && item.sourceFacts.sourceRequestNo === item.sourceRequestNo
      && item.sourceFacts.materialLines.length > 0 && item.sourceFacts.supplierQuotes.length > 0)
  const provider = validateQuoteComparisonProviderContractV1142810().valid
    && providerFacts.sourceProviderCode === 'SCM_SUPPLIER_QUOTE_PROVIDER'
  const page = validateQuoteComparisonPageContractV1142810()
  const boundaries = Object.values(QUOTE_COMPARISON_BOUNDARY).every(value => value === false)
    && walkthrough.supplierRecommendationCreated === false && walkthrough.purchaseOrderCreated === false
    && walkthrough.financeCreated === false && walkthrough.nextPreparation?.supplierRecommendationCreated === false
  const process006A = domain.valid && state && action && page.valid
  const process006B = handoff && provider
  const process006C = providerFacts.factSource === 'SupplierQuoteProvider'
  const process006D = walkthrough.result === 'PASS'
    && walkthrough.steps.map(item => item.stepCode).join('>')
      === 'SUPPLIER_QUOTE>ENTER_QUOTE_COMPARISON>GENERATE_QUOTE_COMPARISON>SAVE_QUOTE_COMPARISON'
  const process008 = boundaries
  const valid = node.valid && process006A && process006B && process006C && process006D && process008
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', status: valid
    ? 'SCM_QUOTE_COMPARISON_RUNTIME_READY' : 'SCM_QUOTE_COMPARISON_RUNTIME_ISSUES_FOUND',
  node, domain, state, action, handoff, provider, page, process006A, process006B, process006C, process006D,
  process008, boundaries })
}
