import { listScmProcessFlowPages } from './scmProcessNavigationContract.js'

export const SCM_ENTERPRISE_READINESS_VERSION = 'V1.14.2.8.4.14'

const DETAILS = Object.freeze({
  'purchase-request': ['PurchaseRequest', 'PurchaseRequestSchema', '/api/procurement/scm-page-facts/purchase-request/'],
  'purchase-inquiry': ['PurchaseInquiry', 'PurchaseInquirySchema', '/api/procurement/scm-page-facts/purchase-inquiry/'],
  'price-approval': ['PriceApproval', 'PriceApprovalSchema', '/api/procurement/scm-page-facts/price-approval/'],
  'purchase-order': ['PurchaseOrder', 'PurchaseOrderSchema', '/api/procurement/scm-page-facts/purchase-order/'],
  'purchase-receive-preview': ['PurchaseReceipt', 'PurchaseReceiveSchema', '/api/procurement/scm-page-facts/purchase-receive-preview/'],
  'incoming-inspection': ['PurchaseInspection', 'IncomingInspectionSchema', '/api/procurement/scm-page-facts/incoming-inspection/'],
  'inventory-balances': ['InventoryBalance', 'InventoryBalanceSchema', '/api/procurement/formal-inventory-facts/'],
  'supplier-reconciliation': ['SupplierReconciliation', 'SupplierReconciliationSchema', '/api/scm/supplier-reconciliations/'],
  'supplier-reconciliation-differences': ['SupplierReconciliationDifference', 'SupplierReconciliationDifferenceSchema', '/api/scm/supplier-reconciliation-differences/'],
  'supplier-reconciliation-confirmations': ['SupplierReconciliationConfirmation', 'SupplierReconciliationConfirmationSchema', '/api/scm/supplier-reconciliation-confirmations/'],
  'supplier-payable-confirmation': ['SupplierPayableConfirmation', 'SupplierPayableConfirmationSchema', '/api/scm/supplier-payable-confirmations/'],
  'supplier-payment-request': ['SupplierPaymentRequest', 'SupplierPaymentRequestSchema', '/api/scm/supplier-payment-requests/'],
  'supplier-payment-status': ['SupplierPaymentStatus', 'SupplierPaymentStatusSchema', '/api/scm/supplier-payment-status/'],
  'supplier-settlement-completion': ['SupplierSettlementCompletion', 'SupplierSettlementCompletionSchema', '/api/scm/supplier-settlement-completions/'],
  'supplier-performance': ['SupplierPerformance', 'SupplierPerformanceSchema', '/api/scm/supplier-performance/'],
  'buyer-performance': ['BuyerPerformance', 'BuyerPerformanceSchema', '/api/scm/buyer-performance/'],
})

const SPECS = Object.freeze(listScmProcessFlowPages().map((page) => {
  const [businessObject, schema, apiEndpoint] = DETAILS[page.pageCode] || []
  return Object.freeze({
    version: SCM_ENTERPRISE_READINESS_VERSION,
    moduleCode: 'SCM',
    pageCode: page.pageCode,
    pageName: page.pageName,
    pageUrl: page.pageUrl,
    sequence: page.sequence,
    businessObject,
    schema,
    apiEndpoint,
    navigationResolver: 'scmProcessNavigationContract',
    factSource: 'server',
  })
}))

export function listScmEnterpriseReadinessPages() {
  return SPECS.map((item) => ({ ...item }))
}

export function resolveScmEnterpriseReadinessPage(pageCodeOrUrl = '') {
  const normalized = String(pageCodeOrUrl || '').split('?')[0]
  const item = SPECS.find((entry) => entry.pageCode === normalized || entry.pageUrl === normalized)
  return item ? { ...item } : null
}
