import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { QUOTE_COMPARISON_NODE_CODE } from './quoteComparisonNodeRuntimeContract.js'

const base = {
  nodeCode: QUOTE_COMPARISON_NODE_CODE,
  objectType: 'QuoteComparison',
  stateModel: 'QUOTE_COMPARISON_RUNTIME_STATE',
}

export const QUOTE_COMPARISON_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'CREATE_QUOTE_COMPARISON_CONTEXT',
    actionName: 'Create Quote Comparison Context',
    buttonCode: 'create-quote-comparison-context',
    allowedFromStates: ['supplier_quotes_ready'],
    resultState: 'comparison_context_created',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'GENERATE_QUOTE_COMPARISON_FACT',
    actionName: 'Generate Quote Comparison Fact',
    buttonCode: 'generate-quote-comparison-fact',
    allowedFromStates: ['comparison_context_created'],
    resultState: 'comparing',
  }),
  createProcessActionRuntimeContract({
    ...base,
    actionCode: 'SAVE_QUOTE_COMPARISON',
    actionName: 'Save Quote Comparison',
    buttonCode: 'save-quote-comparison',
    allowedFromStates: ['comparing'],
    resultState: 'comparison_completed',
  }),
])

export const QUOTE_COMPARISON_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_QUOTE_COMPARISON_CONTEXT',
  generateFact: 'GENERATE_QUOTE_COMPARISON_FACT',
  saveComparison: 'SAVE_QUOTE_COMPARISON',
})
