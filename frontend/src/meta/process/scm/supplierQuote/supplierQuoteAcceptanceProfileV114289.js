import { validateSupplierQuoteNodeContract } from './supplierQuoteNodeContractV114289.js'
import { validateSupplierQuoteDomain } from './supplierQuoteDomainModelV114289.js'
import { SUPPLIER_QUOTE_STATES, SUPPLIER_QUOTE_STATE_BOUNDARY } from './supplierQuoteStateContractV114289.js'
import { SUPPLIER_QUOTE_ACTION_CONTRACTS_V114289, SUPPLIER_QUOTE_FORBIDDEN_ACTIONS } from './supplierQuoteActionContractsV114289.js'
import { createQuotePreparationToSupplierQuoteHandoff } from './quotePreparationToSupplierQuoteHandoffContract.js'
import { validateSupplierQuoteProviderContract } from './supplierQuoteProviderContractV114289.js'
import { validateSupplierQuotePageContract } from './supplierQuotePageContractV114289.js'
import { createSupplierQuoteProvider } from '../../../providers/supplierQuoteProviderV114289.js'
import { executeCompleteSupplierQuote, executeCreateSupplierQuoteContext,
  executeSaveSupplierQuote } from '../../../runtime/supplierQuoteActionRuntimeV114289.js'

export const SUPPLIER_QUOTE_ACCEPTANCE_VERSION = 'V1.14.2.8.18.9'

export async function runSupplierQuoteBusinessWalkthrough({ preparation, quotes, store }) {
  const steps = []
  const record = (stepCode, result, facts = {}) => {
    const step = Object.freeze({ sequence: steps.length + 1, stepCode, result, facts })
    steps.push(step)
    return step
  }
  const source = preparation?.quotePreparationNo ? 'PASS' : 'FAIL'
  record('PRICE_APPROVAL_PREPARATION', source, { quotePreparationNo: preparation?.quotePreparationNo })
  if (source === 'FAIL') return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })

  const created = executeCreateSupplierQuoteContext(preparation, store)
  record('ENTER_SUPPLIER_QUOTE', created.result, { contextNo: created.context?.supplierQuoteContextNo })
  if (created.result === 'FAIL') return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })

  let context = created.context
  for (const input of quotes) {
    const saved = executeSaveSupplierQuote(context, input, store)
    record('SAVE_SUPPLIER_QUOTE', saved.result, { materialCode: input.materialCode, supplierCode: input.supplierCode })
    if (saved.result === 'FAIL') return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })
    context = saved.context
  }
  const completed = executeCompleteSupplierQuote(context, store)
  record('COMPLETE_SUPPLIER_QUOTE', completed.result, { status: completed.context?.quoteStatus })
  return Object.freeze({ result: completed.result, steps: Object.freeze(steps), context: completed.context,
    comparisonPreparation: completed.comparisonPreparation, supplierApiCalled: false,
    supplierSent: false, quoteComparisonCreated: false, purchaseOrderCreated: false })
}

export function validateSupplierQuoteAcceptance({ preparation, walkthrough, store }) {
  const handoff = createQuotePreparationToSupplierQuoteHandoff(preparation)
  const provider = createSupplierQuoteProvider({ store }).load()
  const node = validateSupplierQuoteNodeContract()
  const domain = validateSupplierQuoteDomain(walkthrough.context, store.listQuotes()[0])
  const state = SUPPLIER_QUOTE_STATES.join('>') === [
    'quote_preparation_ready', 'supplier_quote_collecting', 'supplier_quote_completed', 'comparison_ready',
  ].join('>') && walkthrough.context?.quoteStatus === 'comparison_ready'
  const action = Object.keys(SUPPLIER_QUOTE_ACTION_CONTRACTS_V114289).length === 3
    && SUPPLIER_QUOTE_FORBIDDEN_ACTIONS.includes('SEND_SUPPLIER')
    && SUPPLIER_QUOTE_FORBIDDEN_ACTIONS.includes('CREATE_PURCHASE_ORDER')
  const boundaries = Object.values(SUPPLIER_QUOTE_STATE_BOUNDARY).every(value => value === false)
    && walkthrough.supplierApiCalled === false && walkthrough.supplierSent === false
    && walkthrough.quoteComparisonCreated === false && walkthrough.purchaseOrderCreated === false
  const providerValid = validateSupplierQuoteProviderContract().valid
    && provider.contextCount === 1
    && provider.quoteCount === preparation.materialSupplierCandidates.length
  const page = validateSupplierQuotePageContract()
  const process006A = domain.valid && state && action && page.valid
  const process006B = handoff.valid && providerValid
  const process006C = provider.factSource === 'supplier_quote_runtime_store'
  const process006D = walkthrough.result === 'PASS'
    && walkthrough.steps[0]?.stepCode === 'PRICE_APPROVAL_PREPARATION'
    && walkthrough.steps.at(-1)?.stepCode === 'COMPLETE_SUPPLIER_QUOTE'
  const process008 = boundaries
  const valid = node.valid && domain.valid && state && action && handoff.valid && providerValid && page.valid
    && process006A && process006B && process006C && process006D && process008
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', status: valid
    ? 'SCM_SUPPLIER_QUOTE_RUNTIME_READY' : 'SCM_SUPPLIER_QUOTE_RUNTIME_ISSUES_FOUND',
  node, domain, state, action, handoff, provider: providerValid, page,
  process006A, process006B, process006C, process006D, process008, boundaries })
}
