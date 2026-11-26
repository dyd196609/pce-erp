import { checkPurchaseOrderIssueRequirements } from '../process/scm/purchaseOrderIssuePreparation/purchaseOrderIssuePreparationRules.js'

export const PURCHASE_ORDER_ISSUE_PREPARATION_RUNTIME_VERSION = 'V1.14.2.8.16'

const contexts = []
const preparations = []

export function createPurchaseOrderIssuePreparationContext(transaction = {}) {
  if (transaction.objectType !== 'PurchaseOrderTransaction' || transaction.status !== 'draft'
    || !transaction.purchaseDetails?.length) {
    throw new Error('PURCHASE_ORDER_TRANSACTION_NOT_READY_FOR_ISSUE_PREPARATION')
  }
  const deliveryRequirements = Object.freeze(transaction.purchaseDetails.map(item => Object.freeze({
    quoteNo: item.quoteNo, materialCode: item.materialCode,
    deliveryDate: item.deliveryDate, validUntil: item.validUntil,
  })))
  const existing = contexts.find(item => item.transactionNo === transaction.transactionNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'PurchaseOrderIssuePreparationContext',
    contextCode: `POIPC-${transaction.transactionNo}`,
    transactionNo: transaction.transactionNo,
    transactionStatus: transaction.status,
    supplier: transaction.supplier,
    orderDetails: transaction.purchaseDetails,
    totalQuantity: transaction.totalQuantity,
    amountReference: transaction.amountReference,
    deliveryRequirements,
    sourceChain: Object.freeze({ ...transaction.sourceChain, transactionNo: transaction.transactionNo }),
    status: 'issue_context_created',
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

export function checkPurchaseOrderIssuePreparation(context = {}) {
  const result = checkPurchaseOrderIssueRequirements(context)
  const preparation = Object.freeze({
    objectType: 'PurchaseOrderIssuePreparation',
    preparationNo: `POIP-${context.transactionNo}`,
    contextCode: context.contextCode,
    transactionNo: context.transactionNo,
    supplier: context.supplier,
    orderDetails: context.orderDetails,
    totalQuantity: context.totalQuantity,
    amountReference: context.amountReference,
    deliveryRequirements: context.deliveryRequirements,
    sourceChain: context.sourceChain,
    ready: result.ready,
    checks: result.checks,
    blockedReasons: result.blockedReasons,
    status: 'checking',
    preparationOnly: true,
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  preparations.push(preparation)
  return preparation
}

export function savePurchaseOrderIssuePreparation(preparation = {}) {
  if (preparation.objectType !== 'PurchaseOrderIssuePreparation' || preparation.status !== 'checking'
    || !preparation.checks?.length) {
    throw new Error('PURCHASE_ORDER_ISSUE_PREPARATION_NOT_READY_TO_SAVE')
  }
  const saved = Object.freeze({
    ...preparation,
    status: preparation.ready ? 'ready_for_issue' : 'blocked',
    purchaseOrderIssued: false,
    supplierSent: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
    persistenceMode: 'session_runtime',
  })
  const index = preparations.findIndex(item => item.preparationNo === preparation.preparationNo)
  if (index >= 0) preparations.splice(index, 1, saved)
  return Object.freeze({ result: 'PASS', saved: true, object: saved, productionDataWritten: false })
}

export function listPurchaseOrderIssuePreparationContexts() {
  return Object.freeze([...contexts])
}

export function listPurchaseOrderIssuePreparations() {
  return Object.freeze([...preparations])
}
