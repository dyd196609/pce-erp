export const PURCHASE_RECONCILIATION_STATUS_LABELS = Object.freeze({
  not_checked: '待对账',
  pending: '待对账',
  draft: '草稿',
  matched: '对账一致',
  difference_found: '发现差异',
  source_missing: '来源缺失',
})

export function getPurchaseReconciliationStatusLabel(status = '') {
  return PURCHASE_RECONCILIATION_STATUS_LABELS[String(status || '')] || '待对账'
}

export function evaluatePurchaseInvoicePrepareNavigation(record = {}) {
  const status = String(record.reconciliationStatus || record.status || '')
  const eligibility = record.invoicePrepareEligibility || {}
  const hasValue = (value) => Boolean(String(value || '').trim() && String(value || '').trim() !== '-')
  const sourceComplete = [record.sourceSettlementNo, record.purchaseOrderNo, record.supplierName].every(hasValue)

  if (status !== 'matched') return { allowed: false, reason: `当前状态“${getPurchaseReconciliationStatusLabel(status)}”不允许进入采购发票准备。` }
  if (!eligibility.eligible || eligibility.nextStepReadiness !== 'ready_for_invoice_prepare') {
    return { allowed: false, reason: `服务端未放行：${(eligibility.blockingReasons || ['PRC_ELIGIBILITY_BLOCKED']).join(', ')}` }
  }
  if (!sourceComplete) return { allowed: false, reason: '来源供应商结算、采购订单或供应商信息不完整。' }
  return { allowed: true, reason: '' }
}

export function buildPurchaseInvoicePrepareRoute(record = {}) {
  return {
    path: '/finance/purchase-invoice-prepares',
    query: {
      sourcePurchaseReconciliationNo: record.reconciliationNo || '',
      sourceSettlementNo: record.sourceSettlementNo || '',
      purchaseOrderNo: record.purchaseOrderNo || '',
      supplierName: record.supplierName || '',
      reconciliationStatus: record.reconciliationStatus || '',
    },
  }
}
