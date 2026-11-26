import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE } from './purchaseOrderIssueExecutionNodeRuntimeContract.js'

const base = { nodeCode: PURCHASE_ORDER_ISSUE_EXECUTION_NODE_CODE,
  objectType: 'PurchaseOrderIssueAuthorization', stateModel: 'PURCHASE_ORDER_ISSUE_EXECUTION_STATE' }

export const PURCHASE_ORDER_ISSUE_EXECUTION_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_ISSUE_EXECUTION_CONTEXT', actionName: 'Create Issue Execution Context',
    buttonCode: 'create-issue-execution-context', allowedFromStates: ['issue_boundary_decided'],
    resultState: 'execution_context_created' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CHECK_EXECUTION_AUTHORIZATION', actionName: 'Check Execution Authorization',
    buttonCode: 'check-execution-authorization', allowedFromStates: ['execution_context_created'],
    resultState: 'authorization_checking' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'SAVE_EXECUTION_PREPARATION', actionName: 'Save Execution Preparation',
    buttonCode: 'save-execution-preparation', allowedFromStates: ['authorization_checking'], resultState: 'authorized' }),
])

export const PURCHASE_ORDER_ISSUE_EXECUTION_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_ISSUE_EXECUTION_CONTEXT',
  checkAuthorization: 'CHECK_EXECUTION_AUTHORIZATION',
  savePreparation: 'SAVE_EXECUTION_PREPARATION',
})
