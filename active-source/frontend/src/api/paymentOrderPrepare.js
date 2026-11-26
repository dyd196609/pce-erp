import request from './request.js'

export const paymentOrderPrepareApi = Object.freeze({
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/payment-order-prepares/', params, meta: { module: 'finance', factLoad: true } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  bySource(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/by-source/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  generate(data) {
    return request({ method: 'POST', url: '/api/finance/payment-order-prepares/generate', data, meta: { module: 'finance' } })
  },
  saveOrderData(id, data) {
    return request({ method: 'PUT', url: `/api/finance/payment-order-prepares/${encodeURIComponent(id)}/order-data`, data, meta: { module: 'finance' } })
  },
  validate(id, data) {
    return request({ method: 'POST', url: `/api/finance/payment-order-prepares/${encodeURIComponent(id)}/validate`, data, meta: { module: 'finance' } })
  },
  eligibility(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/${encodeURIComponent(id)}/payment-order-draft-eligibility`, meta: { module: 'finance' } })
  },
  validationIssues(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/${encodeURIComponent(id)}/validation-issues`, meta: { module: 'finance' } })
  },
  generationResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/generation-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  orderDataResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/order-data-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  validationResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-order-prepares/validation-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
})
