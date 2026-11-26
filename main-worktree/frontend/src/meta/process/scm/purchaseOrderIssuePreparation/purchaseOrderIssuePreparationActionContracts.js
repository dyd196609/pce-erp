import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE } from './purchaseOrderIssuePreparationNodeRuntimeContract.js'

const base = { nodeCode: PURCHASE_ORDER_ISSUE_PREPARATION_NODE_CODE,
  objectType: 'PurchaseOrderIssuePreparation', stateModel: 'PURCHASE_ORDER_ISSUE_PREPARATION_STATE' }

export const PURCHASE_ORDER_ISSUE_PREPARATION_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_ISSUE_PREPARATION_CONTEXT', actionName: 'Create Issue Preparation Context',
    buttonCode: 'create-issue-preparation-context', allowedFromStates: ['purchase_order_transaction_draft'],
    resultState: 'issue_context_created' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CHECK_ISSUE_REQUIREMENTS', actionName: 'Check Issue Requirements',
    buttonCode: 'check-issue-requirements', allowedFromStates: ['issue_context_created'], resultState: 'checking' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'SAVE_ISSUE_PREPARATION', actionName: 'Save Issue Preparation',
    buttonCode: 'save-issue-preparation', allowedFromStates: ['checking'], resultState: 'ready_for_issue' }),
])

export const PURCHASE_ORDER_ISSUE_PREPARATION_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_ISSUE_PREPARATION_CONTEXT',
  checkRequirements: 'CHECK_ISSUE_REQUIREMENTS',
  savePreparation: 'SAVE_ISSUE_PREPARATION',
})
