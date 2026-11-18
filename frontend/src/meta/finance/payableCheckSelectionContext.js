export const PAYABLE_CHECK_SELECTION_CONTEXT_VERSION = 'V1.14.2.8.4.6'

export function payableCheckSettlementBlockedReason(record = {}) {
  if (!record?.payableCheckNo) return '当前记录尚未生成应付核对单，不能进入供应商结算。'
  if (!['checked', 'matched', 'invoicePrepareReady', 'invoicePrepared'].includes(record.checkStatus)) {
    return '当前应付核对尚未完成，不能进入供应商结算。'
  }
  return ''
}

export function resolveSupplierSettlementSelection(selectedRows = []) {
  if (!selectedRows.length) {
    return { allowed: false, record: null, reason: '请选择一条采购应付核对记录。' }
  }
  if (selectedRows.length !== 1) {
    return { allowed: false, record: null, reason: '供应商结算需要单条来源上下文，请仅选择1条记录。' }
  }
  const record = selectedRows[0]
  const reason = payableCheckSettlementBlockedReason(record)
  return { allowed: !reason, record, reason }
}

export function buildSupplierSettlementRoute(record = {}) {
  const reason = payableCheckSettlementBlockedReason(record)
  if (reason) throw new Error(reason)
  return {
    path: '/scm/supplier-settlements',
    query: {
      sourcePayableCheckNo: record.payableCheckNo,
      sourcePayablePrepareNo: record.sourcePayablePrepareNo || '',
      purchaseOrderNo: record.sourcePurchaseOrderNo || record.purchaseOrderNo || '',
      supplierId: record.supplierId || '',
      supplierName: record.supplierName || '',
      sourceStatus: record.checkStatus || '',
    },
  }
}
