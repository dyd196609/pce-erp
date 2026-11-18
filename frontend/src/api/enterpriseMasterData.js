import request from './request'

export const enterpriseMasterDataApi = {
  validatedFactFormalization(method = 'GET') {
    return request({
      method,
      url: '/api/masterdata/validated-fact-formalization/',
      meta: { module: 'masterdata', explicitBusinessAction: method === 'POST' },
    })
  },
  baseDataReadiness() {
    return request({
      method: 'GET',
      url: '/api/masterdata/base-data-readiness/',
      meta: { module: 'masterdata' },
    })
  },
  baseDataComparison(entityCode) {
    return request({
      method: 'GET',
      url: `/api/masterdata/base-data-comparison/${encodeURIComponent(entityCode)}/`,
      meta: { module: 'masterdata' },
    })
  },
  group2Comparison(entityCode) {
    return request({
      method: 'GET',
      url: `/api/masterdata/group2-comparison/${encodeURIComponent(entityCode)}/`,
      meta: { module: 'masterdata' },
    })
  },
  group3Comparison(entityCode) {
    return request({
      method: 'GET',
      url: `/api/masterdata/group3-comparison/${encodeURIComponent(entityCode)}/`,
      meta: { module: 'masterdata' },
    })
  },
  group3AOperationTargetedRevalidation() {
    return request({
      method: 'GET',
      url: '/api/masterdata/group3a-operation-targeted-revalidation/',
      meta: { module: 'masterdata' },
    })
  },
  supplierMaterialPrices(params = {}) {
    return request({
      method: 'GET',
      url: '/api/masterdata/prices/supplier-material-prices/runtime/facts/',
      params,
      meta: { module: 'masterdata' },
    })
  },
  confirmSupplierQuotationPrice(data) {
    return request({
      method: 'POST',
      url: '/api/masterdata/prices/supplier-material-prices/runtime/confirm-quotation/',
      data,
      meta: { module: 'masterdata' },
    })
  },
  supplierPriceFacts() {
    return request({
      method: 'GET',
      url: '/api/masterdata/prices/supplier-price-facts/runtime/facts/',
      meta: { module: 'masterdata' },
    })
  },
  materialSupplierRelations() {
    return request({
      method: 'GET',
      url: '/api/masterdata/relations/material-suppliers/runtime/facts/',
      meta: { module: 'masterdata' },
    })
  },
  statistics() {
    return request({
      method: 'GET',
      url: '/api/masterdata/statistics/runtime/facts/',
      meta: { module: 'masterdata' },
    })
  },
  facts(entityCode, params = {}) {
    return request({
      method: 'GET',
      url: `/api/masterdata/enterprise/${entityCode}/facts/`,
      params,
      meta: { module: 'masterdata' },
    })
  },
  recordPriceApprovalResult(data) {
    return request({
      url: '/api/masterdata/prices/supplier-material-prices/runtime/approval-results/',
      method: 'post',
      data,
    })
  },
  batchArchiveSupplierMaterialPrices(resultIds) {
    return request({
      url: '/api/masterdata/prices/supplier-material-prices/runtime/batch-archive/',
      method: 'post',
      data: { resultIds },
    })
  },
  archivePriceApprovalPreparations(items) {
    return request({
      url: '/api/masterdata/prices/supplier-material-prices/runtime/price-approval-preparations/archive/',
      method: 'post',
      data: { items },
      meta: { module: 'masterdata', explicitBusinessAction: true },
    })
  },
  priceSourceConsistency() {
    return request({
      url: '/api/masterdata/prices/supplier-material-prices/runtime/price-source-consistency/',
      method: 'get',
      meta: { module: 'masterdata' },
    })
  },
  updateSupplierMaterialPrice(priceNo, data) {
    return request({
      url: `/api/masterdata/prices/supplier-material-prices/runtime/${encodeURIComponent(priceNo)}/maintenance/`,
      method: 'patch', data,
      meta: { module: 'masterdata', explicitBusinessAction: true },
    })
  },
  createSupplierMaterialPrice(data) {
    return request({
      url: '/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/',
      method: 'post', data,
      meta: { module: 'masterdata', explicitBusinessAction: true },
    })
  },
  updateMaterialSupplierDeliveryPeriod(relationCode, deliveryPeriod) {
    return request({
      url: `/api/masterdata/relations/material-suppliers/runtime/${encodeURIComponent(relationCode)}/maintenance/`,
      method: 'post', data: { deliveryPeriod },
      meta: { module: 'masterdata', explicitBusinessAction: true },
    })
  },
}
