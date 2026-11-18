import { checkPurchaseOrderIssueExecutionAuthorization } from '../process/scm/purchaseOrderIssueExecution/purchaseOrderIssueExecutionRules.js'

export const PURCHASE_ORDER_ISSUE_EXECUTION_RUNTIME_VERSION = 'V1.14.2.8.18'

const contexts = []
const authorizations = []

export function createPurchaseOrderIssueExecutionContext(issueDecision = {}) {
  if (issueDecision.objectType !== 'PurchaseOrderIssueDecision'
    || !['allowed', 'blocked'].includes(issueDecision.status) || !issueDecision.checks?.length) {
    throw new Error('PURCHASE_ORDER_ISSUE_DECISION_NOT_READY_FOR_EXECUTION_AUTHORIZATION')
  }
  const existing = contexts.find(item => item.issueDecisionNo === issueDecision.issueDecisionNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'PurchaseOrderIssueExecutionContext',
    contextCode: `POIEC-${issueDecision.issueDecisionNo}`,
    issueDecisionNo: issueDecision.issueDecisionNo,
    orderInformation: issueDecision.orderInformation,
    supplierInformation: issueDecision.supplier,
    authorizationEvidence: Object.freeze({ boundaryStatus: issueDecision.status,
      issuePermissionGranted: issueDecision.issuePermissionGranted,
      checks: issueDecision.checks, blockedReasons: issueDecision.blockedReasons,
      boundaryEvidence: issueDecision.evidence }),
    sourceChain: issueDecision.sourceChain,
    executionIsolation: Object.freeze({ supplierApiEnabled: false,
      purchaseOrderIssueEnabled: false, productionEndpointConnected: false }),
    status: 'execution_context_created',
    supplierApiCalled: false,
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  contexts.push(context)
  return context
}

export function checkPurchaseOrderIssueExecution(context = {}) {
  const result = checkPurchaseOrderIssueExecutionAuthorization(context)
  const authorization = Object.freeze({
    objectType: 'PurchaseOrderIssueAuthorization',
    authorizationNo: `POIA-${context.issueDecisionNo}`,
    contextCode: context.contextCode,
    issueDecisionNo: context.issueDecisionNo,
    orderInformation: context.orderInformation,
    supplierInformation: context.supplierInformation,
    authorizationEvidence: context.authorizationEvidence,
    sourceChain: context.sourceChain,
    authorized: result.authorized,
    checks: result.checks,
    blockedReasons: result.blockedReasons,
    status: 'authorization_checking',
    authorizationPreparationOnly: true,
    supplierApiCalled: false,
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  authorizations.push(authorization)
  return authorization
}

export function savePurchaseOrderIssueExecutionPreparation(authorization = {}) {
  if (authorization.objectType !== 'PurchaseOrderIssueAuthorization'
    || authorization.status !== 'authorization_checking' || !authorization.checks?.length) {
    throw new Error('PURCHASE_ORDER_ISSUE_AUTHORIZATION_NOT_READY_TO_SAVE')
  }
  const saved = Object.freeze({
    ...authorization,
    status: authorization.authorized ? 'authorized' : 'blocked',
    executionAuthorized: authorization.authorized,
    authorizationPreparationOnly: true,
    supplierApiCalled: false,
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = authorizations.findIndex(item => item.authorizationNo === authorization.authorizationNo)
  if (index >= 0) authorizations.splice(index, 1, saved)
  return Object.freeze({ result: 'PASS', saved: true, object: saved, productionDataWritten: false })
}

export function listPurchaseOrderIssueExecutionContexts() {
  return Object.freeze([...contexts])
}

export function listPurchaseOrderIssueAuthorizations() {
  return Object.freeze([...authorizations])
}
