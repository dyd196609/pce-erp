import request from './request'

export function getPurchaseCanaryContext(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/context',
    params,
    meta: { module: 'purchase-canary' },
  })
}

export function listPurchaseCanaryScenarios(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/scenarios',
    params,
    meta: { module: 'purchase-canary' },
  })
}

export function getCanaryOperationData(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/operation-data',
    params,
    meta: { module: 'purchase-canary-operation-data' },
  })
}

export function getPurchaseInquiryCanaryRuntime(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/purchase-inquiry-runtime',
    params,
    meta: { module: 'purchase-inquiry-canary', factLoad: true, readOnly: true },
  })
}

export function getSupplierQuotationCanaryRuntime(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/supplier-quotation-runtime',
    params,
    meta: { module: 'supplier-quotation-canary', factLoad: true, readOnly: true },
  })
}

export function getQuoteComparisonCanaryRuntime(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/quote-comparison-runtime',
    params,
    meta: { module: 'quote-comparison-canary', factLoad: true, readOnly: true },
  })
}

export function getPriceApprovalCanaryRuntime(params = {}) {
  return request({
    method: 'GET',
    url: '/api/pce/purchase-canary/price-approval-runtime',
    params,
    meta: { module: 'price-approval-canary', factLoad: true, readOnly: true },
  })
}
