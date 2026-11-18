export const PURCHASE_ORDER_DETAIL_ACCEPTANCE_VERSION_V1142842725 = 'V1.14.2.8.4.27.2.5'
export const PURCHASE_ORDER_DETAIL_VIEW_CODE_V1142842725 = 'PurchaseOrderDetailView'

export const PURCHASE_ORDER_DETAIL_REGIONS_V1142842725 = Object.freeze([
  Object.freeze({ code: 'basic', label: '采购订单基础信息', requiredFields: Object.freeze([
    'purchaseOrderNo', 'supplierName', 'statusLabel', 'totalQuantity', 'plannedDeliveryDate',
  ]) }),
  Object.freeze({ code: 'source-relations', label: '来源关系', requiredFields: Object.freeze([
    'sourceGateNo', 'sourcePurchaseRequestIds',
  ]) }),
  Object.freeze({ code: 'material-detail', label: '采购物料明细', requiredFields: Object.freeze([
    'materialCode', 'materialName', 'quantity', 'plannedDeliveryDate', 'receiptStatusLabel',
  ]) }),
  Object.freeze({ code: 'lifecycle', label: '生命周期状态', requiredFields: Object.freeze([
    'lifecycleStatusLabel', 'nextAction',
  ]) }),
  Object.freeze({ code: 'operations', label: '操作区域', requiredFields: Object.freeze([
    'viewRole', 'export', 'printPreview',
  ]) }),
])

export function evaluatePurchaseOrderDetailAcceptanceV1142842725({
  businessView = {}, presentRegionCodes = [],
} = {}) {
  const present = new Set(presentRegionCodes)
  const regionResults = PURCHASE_ORDER_DETAIL_REGIONS_V1142842725.map(region => Object.freeze({
    ...region,
    result: present.has(region.code) ? 'PASS' : 'FAIL',
  }))
  const fieldChecks = Object.freeze({
    objectNo: Boolean(businessView.identity?.objectNo),
    supplierName: Boolean(businessView.baseInfo?.supplierName),
    materialRows: Array.isArray(businessView.materialDetail?.rows),
    itemSource: businessView.materialDetail?.source === 'PurchaseOrderItem[]',
    lifecycleStatus: Boolean(businessView.lifecycle?.lifecycleStatusLabel),
    dataBindingProjectionOnly: businessView.dataProtection?.projectionOnly === true,
  })
  const passed = regionResults.every(item => item.result === 'PASS')
    && Object.values(fieldChecks).every(Boolean)
  return Object.freeze({
    version: PURCHASE_ORDER_DETAIL_ACCEPTANCE_VERSION_V1142842725,
    viewCode: PURCHASE_ORDER_DETAIL_VIEW_CODE_V1142842725,
    regionResults: Object.freeze(regionResults),
    fieldChecks,
    businessWriteCount: 0,
    result: passed ? 'PASS' : 'FAIL',
  })
}
