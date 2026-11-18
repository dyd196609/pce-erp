import request from './request.js'

export const paymentOrderDraftApi = Object.freeze({
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/payment-order-drafts/', params, meta: { module: 'finance', factLoad: true } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  bySource(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/by-source/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  generate(data) {
    return request({ method: 'POST', url: '/api/finance/payment-order-drafts/generate', data, meta: { module: 'finance' } })
  },
  saveOrderData(id, data) {
    return request({ method: 'PUT', url: `/api/finance/payment-order-drafts/${encodeURIComponent(id)}/draft-data`, data, meta: { module: 'finance' } })
  },
  review(id, data) {
    return request({ method: 'POST', url: `/api/finance/payment-order-drafts/${encodeURIComponent(id)}/review`, data, meta: { module: 'finance' } })
  },
  eligibility(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/${encodeURIComponent(id)}/payment-risk-review-eligibility`, meta: { module: 'finance' } })
  },
  reviewIssues(id) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/${encodeURIComponent(id)}/review-issues`, meta: { module: 'finance' } })
  },
  generationResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/generation-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  orderDataResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/draft-data-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  reviewResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-order-drafts/review-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
})
