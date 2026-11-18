export const BUSINESS_SOURCE_TYPE_LABELS = Object.freeze({
  legacy_verified_fact: '历史验收事实',
  development_test_data: '开发测试报价事实',
  SupplierQuotation: '供应商正式报价',
  SupplierQuotationConfirmed: '已确认供应商报价',
  QuoteComparisonFact: '报价比较事实',
  SupplierMaterialPrice: '企业有效价格',
  PriceApprovalResult: '人工核价确认',
  PurchaseOrderHistory: '历史采购执行价格',
})

export function resolveBusinessSourceTypeLabel(value) {
  return BUSINESS_SOURCE_TYPE_LABELS[String(value || '').trim()] || '未登记来源'
}
