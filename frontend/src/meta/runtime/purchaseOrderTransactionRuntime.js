import { validatePurchaseOrderTransactionContextFacts } from '../process/scm/purchaseOrderTransaction/purchaseOrderTransactionRules.js'

export const PURCHASE_ORDER_TRANSACTION_RUNTIME_VERSION = 'V1.14.2.8.15'

const contexts = []
const transactions = []

export function createPurchaseOrderTransactionContext(gateDecision = {}) {
  if (gateDecision.objectType !== 'PurchaseOrderCreationGateDecision'
    || gateDecision.status !== 'eligible' || gateDecision.eligible !== true
    || !gateDecision.purchaseDetails?.length) {
    throw new Error('PURCHASE_ORDER_GATE_NOT_ELIGIBLE_FOR_TRANSACTION')
  }
  const existing = contexts.find(item => item.gateDecisionNo === gateDecision.gateDecisionNo)
  if (existing) return existing
  const context = Object.freeze({
    objectType: 'PurchaseOrderTransactionContext',
    contextCode: `POTC-${gateDecision.gateDecisionNo}`,
    gateDecisionNo: gateDecision.gateDecisionNo,
    gateStatus: gateDecision.status,
    supplier: gateDecision.recommendedSupplier,
    purchaseDetails: Object.freeze(gateDecision.purchaseDetails.map(item => Object.freeze({ ...item }))),
    totalQuantity: gateDecision.totalQuantity,
    amountReference: Object.freeze({ currency: gateDecision.costReference.currency,
      totalAmount: gateDecision.costReference.totalCost, source: gateDecision.costReference.source }),
    sourceChain: Object.freeze({ ...gateDecision.sourceChain,
      recommendationDecisionNo: gateDecision.recommendationDecisionNo,
      gateDecisionNo: gateDecision.gateDecisionNo }),
    status: 'transaction_context_created',
    purchaseOrderExecutionCreated: false,
    supplierPublished: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  const validation = validatePurchaseOrderTransactionContextFacts(context)
  if (!validation.valid) throw new Error(`PURCHASE_ORDER_TRANSACTION_CONTEXT_INVALID:${validation.errors.join(',')}`)
  contexts.push(context)
  return context
}

export function createPurchaseOrderTransaction(context = {}) {
  if (context.objectType !== 'PurchaseOrderTransactionContext' || context.status !== 'transaction_context_created') {
    throw new Error('PURCHASE_ORDER_TRANSACTION_CONTEXT_NOT_READY')
  }
  const validation = validatePurchaseOrderTransactionContextFacts(context)
  if (!validation.valid) throw new Error(`PURCHASE_ORDER_TRANSACTION_CONTEXT_INVALID:${validation.errors.join(',')}`)
  const transaction = Object.freeze({
    objectType: 'PurchaseOrderTransaction',
    transactionNo: `POT-${context.gateDecisionNo}`,
    contextCode: context.contextCode,
    gateDecisionNo: context.gateDecisionNo,
    supplier: context.supplier,
    purchaseDetails: context.purchaseDetails,
    totalQuantity: context.totalQuantity,
    amountReference: context.amountReference,
    sourceChain: context.sourceChain,
    status: 'draft',
    transactionMode: 'session_draft_only',
    purchaseOrderNo: null,
    purchaseOrderExecutionCreated: false,
    supplierPublished: false,
    goodsReceived: false,
    inventoryPosted: false,
    invoiceCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  transactions.push(transaction)
  return transaction
}

export function savePurchaseOrderTransaction(transaction = {}) {
  if (transaction.objectType !== 'PurchaseOrderTransaction' || transaction.status !== 'draft') {
    throw new Error('PURCHASE_ORDER_TRANSACTION_DRAFT_REQUIRED')
  }
  return Object.freeze({
    result: 'BLOCKED',
    saved: false,
    reason: 'PURCHASE_ORDER_TRANSACTION_ADVANCE_LOCKED_V1142815',
    object: transaction,
    stateTransitionExecuted: false,
    productionDataWritten: false,
  })
}

export function listPurchaseOrderTransactionContexts() {
  return Object.freeze([...contexts])
}

export function listPurchaseOrderTransactions() {
  return Object.freeze([...transactions])
}
