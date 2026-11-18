import { createProcessActionRuntimeContract } from '../../contract/processActionRuntimeContract.js'
import { PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE } from './purchaseOrderIssueBoundaryNodeRuntimeContract.js'

const base = { nodeCode: PURCHASE_ORDER_ISSUE_BOUNDARY_NODE_CODE,
  objectType: 'PurchaseOrderIssueDecision', stateModel: 'PURCHASE_ORDER_ISSUE_BOUNDARY_STATE' }

export const PURCHASE_ORDER_ISSUE_BOUNDARY_ACTION_CONTRACTS = Object.freeze([
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'CREATE_ISSUE_BOUNDARY_CONTEXT', actionName: 'Create Issue Boundary Context',
    buttonCode: 'create-issue-boundary-context', allowedFromStates: ['issue_preparation_ready'],
    resultState: 'issue_boundary_context_created' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'EVALUATE_ISSUE_PERMISSION', actionName: 'Evaluate Issue Permission',
    buttonCode: 'evaluate-issue-permission', allowedFromStates: ['issue_boundary_context_created'],
    resultState: 'evaluating' }),
  createProcessActionRuntimeContract({ ...base,
    actionCode: 'SAVE_ISSUE_DECISION', actionName: 'Save Issue Decision',
    buttonCode: 'save-issue-decision', allowedFromStates: ['evaluating'], resultState: 'allowed' }),
])

export const PURCHASE_ORDER_ISSUE_BOUNDARY_UI_ACTION_CODES = Object.freeze({
  createContext: 'CREATE_ISSUE_BOUNDARY_CONTEXT',
  evaluatePermission: 'EVALUATE_ISSUE_PERMISSION',
  saveDecision: 'SAVE_ISSUE_DECISION',
})
