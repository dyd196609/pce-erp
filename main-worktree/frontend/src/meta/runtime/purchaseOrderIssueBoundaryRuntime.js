import { evaluatePurchaseOrderIssuePermission } from '../process/scm/purchaseOrderIssueBoundary/purchaseOrderIssueBoundaryRules.js'

export const PURCHASE_ORDER_ISSUE_BOUNDARY_RUNTIME_VERSION = 'V1.14.2.8.17'

const contexts = []
const decisions = []

export function createPurchaseOrderIssueBoundaryContext(preparation = {}) {
  if (preparation.objectType !== 'PurchaseOrderIssuePreparation'
    || !['ready_for_issue', 'blocked'].includes(preparation.status) || !preparation.checks?.length) {
    throw new Error('PURCHASE_ORDER_ISSUE_PREPARATION_NOT_READY_FOR_BOUNDARY')
  }
  const existing = contexts.find(item => item.preparationNo === preparation.preparationNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'PurchaseOrderIssueBoundaryContext',
    contextCode: `POIBC-${preparation.preparationNo}`,
    preparationNo: preparation.preparationNo,
    supplier: preparation.supplier,
    orderInformation: Object.freeze({ transactionNo: preparation.transactionNo,
      orderDetails: preparation.orderDetails, totalQuantity: preparation.totalQuantity,
      amountReference: preparation.amountReference, deliveryRequirements: preparation.deliveryRequirements }),
    preparationResult: Object.freeze({ status: preparation.status, ready: preparation.ready,
      blockedReasons: preparation.blockedReasons }),
    sourceChain: preparation.sourceChain,
    evidence: Object.freeze({ checks: preparation.checks,
      deliveryRequirements: preparation.deliveryRequirements, preparationNo: preparation.preparationNo }),
    status: 'issue_boundary_context_created',
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

export function evaluatePurchaseOrderIssueBoundary(context = {}) {
  const result = evaluatePurchaseOrderIssuePermission(context)
  const decision = Object.freeze({
    objectType: 'PurchaseOrderIssueDecision',
    issueDecisionNo: `POID-${context.preparationNo}`,
    contextCode: context.contextCode,
    preparationNo: context.preparationNo,
    supplier: context.supplier,
    orderInformation: context.orderInformation,
    sourceChain: context.sourceChain,
    evidence: context.evidence,
    allowed: result.allowed,
    checks: result.checks,
    blockedReasons: result.blockedReasons,
    status: 'evaluating',
    permissionDecisionOnly: true,
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  decisions.push(decision)
  return decision
}

export function savePurchaseOrderIssueDecision(decision = {}) {
  if (decision.objectType !== 'PurchaseOrderIssueDecision' || decision.status !== 'evaluating'
    || !decision.checks?.length) {
    throw new Error('PURCHASE_ORDER_ISSUE_DECISION_NOT_READY_TO_SAVE')
  }
  const saved = Object.freeze({
    ...decision,
    status: decision.allowed ? 'allowed' : 'blocked',
    issuePermissionGranted: decision.allowed,
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = decisions.findIndex(item => item.issueDecisionNo === decision.issueDecisionNo)
  if (index >= 0) decisions.splice(index, 1, saved)
  return Object.freeze({ result: 'PASS', saved: true, object: saved, productionDataWritten: false })
}

export function listPurchaseOrderIssueBoundaryContexts() {
  return Object.freeze([...contexts])
}

export function listPurchaseOrderIssueDecisions() {
  return Object.freeze([...decisions])
}
